"""Exercise the real session store through the HTTP lifecycle."""
from copy import deepcopy
from types import SimpleNamespace
import httpx
import pytest
from api.models.visual_tutor import VisualTutorAction
from api.services.visual_tutor.session_store import VisualTutorSessionStore, BoardVersionConflictError
from tests.test_local_limits_demo import _request, _turn
from tests.test_visual_tutor_routes import _make_app

class MemoryCollection:
    def __init__(self):
        self.documents = {}

    async def find_one(self, query):
        return deepcopy(self.documents.get(query['session_id']))

    async def update_one(self, query, update, upsert=False):
        sid = query['session_id']
        existing = self.documents.get(sid)
        if '$or' in query and not any(existing.get('board_version') == branch.get('board_version') for branch in query['$or']):
            return SimpleNamespace(matched_count=0)
        if existing is None:
            assert upsert
            existing = deepcopy(update.get('$setOnInsert', {}))
            self.documents[sid] = existing
        existing.update(deepcopy(update.get('$set', {})))
        for key, value in update.get('$push', {}).items():
            values = existing.setdefault(key, [])
            values.extend(deepcopy(value['$each']))
            existing[key] = values[value['$slice']:] if value['$slice'] < 0 else values[:value['$slice']]
        return SimpleNamespace(matched_count=1)

@pytest.mark.asyncio
async def test_persisted_limits_lifecycle_retry_restore_and_stale_protection(monkeypatch):
    monkeypatch.setenv('VISUAL_TUTOR_INTERNAL_TOKEN', 'test-visual-tutor-token')
    monkeypatch.setenv('VISUAL_TUTOR_LLM_PROVIDER', 'none')
    # The scripted Limits lesson is off by default; this test exercises it.
    from api.core.config import settings
    monkeypatch.setattr(settings, 'VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED', True)
    store = VisualTutorSessionStore({'visual_tutor_sessions': MemoryCollection()})
    app = _make_app(store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        request = _request().model_copy(update={'user_id': 'student-1', 'session_id': None})
        async def turn(action, *, message='', version=0, key='opening', claimed_step=0):
            payload = request.model_dump(mode='json')
            payload.update(action=action.value, message=message, client_board_version=version, idempotency_key=key)
            payload['current_state']['current_step_index'] = claimed_step
            return await client.post('/api/v1/visual_tutor/turn', json=payload)
        opening = await turn(VisualTutorAction.START)
        assert opening.status_code == 200
        sid = opening.json()['session_id']
        request.session_id = sid
        assert (await store.get_session(sid)).board_version == 1
        assert opening.json()['final_answer_locked']
        correct = await turn(VisualTutorAction.SUBMIT_STEP, message='5', version=1, key='correct')
        assert correct.status_code == 200
        session = await store.get_session(sid)
        assert (session.current_step_index, session.attempts, session.board_version) == (1, 1, 2)
        retry = await turn(VisualTutorAction.SUBMIT_STEP, message='5', version=1, key='correct')
        assert retry.status_code == 200
        assert retry.json()['board_version'] == 2
        assert (await store.get_session(sid)).attempts == 1
        stale = await turn(VisualTutorAction.SUBMIT_STEP, message='5', version=0, key='stale')
        assert stale.status_code == 409
        wrong = await turn(VisualTutorAction.SUBMIT_STEP, message='4', version=2, key='wrong', claimed_step=99)
        assert wrong.status_code == 200
        session = await store.get_session(sid)
        assert (session.current_step_index, session.attempts, session.wrong_attempts) == (1, 2, 1)
        assert wrong.json()['final_answer_locked']
        assert len(wrong.json()['board_actions']) == 2
        for index, action in enumerate((VisualTutorAction.REQUEST_HINT, VisualTutorAction.EXPLAIN_DIFFERENTLY), start=3):
            result = await turn(action, version=index, key=action.value)
            assert result.status_code == 200
            assert 'show_table' in [item['type'] for item in result.json()['board_actions']]
            assert result.json()['final_answer_locked']
        before = await store.get_session(sid)
        restored = await client.get(f'/api/v1/visual_tutor/sessions/{sid}', params={'user_id': 'student-1'})
        assert restored.status_code == 200
        assert restored.json()['current_step_index'] == 1
        assert restored.json()['board_version'] == before.board_version
        assert before.teaching_board_state  # Replay stays private in the store.
        resume = await turn(VisualTutorAction.START, version=5, key='resume')
        assert resume.status_code == 200
        after = await store.get_session(sid)
        assert (after.current_step_index, after.attempts) == (before.current_step_index, before.attempts)
        assert resume.json()['final_answer_locked']

@pytest.mark.asyncio
async def test_store_rejects_explicit_zero_board_version():
    store = VisualTutorSessionStore({'visual_tutor_sessions': MemoryCollection()})
    request = _request()
    await store.persist_turn(request=request, response=_turn())
    request.client_board_version = 0
    with pytest.raises(BoardVersionConflictError):
        await store.persist_turn(request=request, response=_turn())
