"""
Tests for Step Sequencing Routes

Tests the REST API endpoints for teaching workflow:
- POST /step-sequencing/start
- POST /step-sequencing/{session_id}/respond
- GET /step-sequencing/{session_id}
- DELETE /step-sequencing/{session_id}
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from api.main import app
from api.models.problem_models import Problem, ProblemDifficulty, ProblemSubject
from api.models.teaching_step import TeachingPlan, TeachingStep, StepType, Subject
from api.repositories.problem_repository import ProblemRepository
from api.services.step_sequencing_service import StepSequencingService
from api.services.spaced_repetition_service import SpacedRepetitionService
from api.routes import step_sequencing


# Create test client
client = TestClient(app)


@pytest.fixture
def problem_repository():
    """Fixture for problem repository"""
    return ProblemRepository()


@pytest.fixture
def step_sequencing_service():
    """Fixture for step sequencing service"""
    return StepSequencingService()


@pytest.fixture
def spaced_repetition_service():
    """Fixture for spaced repetition service"""
    return SpacedRepetitionService()


@pytest.fixture(autouse=True)
def initialize_services(problem_repository, step_sequencing_service, spaced_repetition_service):
    """Initialize services for all tests"""
    step_sequencing.initialize_services(
        step_sequencing_service,
        problem_repository,
        spaced_repetition_service
    )
    yield
    # Cleanup: clear sessions
    step_sequencing._sessions.clear()


class TestStartTeaching:
    """Tests for POST /step-sequencing/start endpoint"""
    
    def test_start_teaching_success(self):
        """Test successful teaching session start"""
        request_body = {
            "problem_id": "math_linear_001",
            "student_id": "student_001",
            "learning_style": "visual",
            "include_hints": True,
        }
        
        response = client.post("/step-sequencing/start", json=request_body)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "session_id" in data
        assert "problem" in data
        assert "current_step" in data
        assert "total_steps" in data
        assert "teaching_plan_id" in data
        
        # Verify session_id format
        assert data["session_id"].startswith("sess_")
        
        # Verify problem loaded
        assert data["problem"]["id"] == "math_linear_001"
        assert data["problem"]["subject"] == "mathematics"
        
        # Verify first step
        assert data["current_step"]["step_number"] == 1
        assert "title" in data["current_step"]
        assert "description" in data["current_step"]
        
        # Verify total steps > 0
        assert data["total_steps"] > 0
    
    def test_start_teaching_problem_not_found(self):
        """Test starting teaching with non-existent problem"""
        request_body = {
            "problem_id": "nonexistent_problem",
            "student_id": "student_001",
        }
        
        response = client.post("/step-sequencing/start", json=request_body)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_start_teaching_creates_session(self):
        """Test that session is created in storage"""
        request_body = {
            "problem_id": "math_linear_001",
            "student_id": "student_001",
        }
        
        response = client.post("/step-sequencing/start", json=request_body)
        assert response.status_code == 200
        
        session_id = response.json()["session_id"]
        
        # Verify session exists in storage
        assert session_id in step_sequencing._sessions
        
        session = step_sequencing._sessions[session_id]
        assert session["problem_id"] == "math_linear_001"
        assert session["student_id"] == "student_001"
        assert session["current_step_number"] == 1
        assert session["correct_responses"] == 0
        assert session["incorrect_responses"] == 0
        assert session["is_complete"] == False


class TestRespondToStep:
    """Tests for POST /step-sequencing/{session_id}/respond endpoint"""
    
    def test_respond_to_step_success(self):
        """Test successful response to a step"""
        # First, start a teaching session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        
        # Now respond to the step
        respond_body = {
            "student_response": "Addition",
            "response_type": "text",
            "confidence_level": "medium",
            "time_spent_seconds": 30,
        }
        
        response = client.post(
            f"/step-sequencing/{session_id}/respond",
            json=respond_body
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "is_correct" in data
        assert "feedback" in data
        assert "confidence" in data
        assert "session_complete" in data
        
        # Verify confidence is a float between 0 and 1
        assert isinstance(data["confidence"], float)
        assert 0 <= data["confidence"] <= 1
    
    def test_respond_to_nonexistent_session(self):
        """Test responding to a non-existent session"""
        respond_body = {
            "student_response": "x = 4",
            "response_type": "text",
        }
        
        response = client.post(
            "/step-sequencing/nonexistent_session/respond",
            json=respond_body
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_respond_advances_step_on_correct(self):
        """Test that correct response advances to next step"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        initial_step = start_response.json()["current_step"]["step_number"]
        
        # Get session data
        session = step_sequencing._sessions[session_id]
        
        # Respond with a likely correct answer
        respond_body = {
            "student_response": "addition",
            "response_type": "text",
        }
        
        response = client.post(
            f"/step-sequencing/{session_id}/respond",
            json=respond_body
        )
        
        assert response.status_code == 200
        
        # If response was correct, check that step advanced or session complete
        if response.json()["is_correct"]:
            # Either next_step exists or session_complete is True
            assert response.json()["next_step"] or response.json()["session_complete"]
    
    def test_session_completes_after_all_steps(self):
        """Test that session completes after all steps"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        
        # Skip through steps (simulate by forcing completion)
        session = step_sequencing._sessions[session_id]
        
        # Set session as complete
        session["is_complete"] = True
        
        # Try to respond to completed session
        respond_body = {
            "student_response": "test",
            "response_type": "text",
        }
        
        response = client.post(
            f"/step-sequencing/{session_id}/respond",
            json=respond_body
        )
        
        assert response.status_code == 200
        assert response.json()["session_complete"] == True


class TestSessionStatus:
    """Tests for GET /step-sequencing/{session_id} endpoint"""
    
    def test_get_session_status_success(self):
        """Test getting session status"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        total_steps = start_response.json()["total_steps"]
        
        # Get status
        response = client.get(f"/step-sequencing/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["session_id"] == session_id
        assert data["problem_id"] == "math_linear_001"
        assert data["student_id"] == "student_001"
        assert data["current_step_number"] == 1
        assert data["total_steps"] == total_steps
        assert data["progress_percent"] == pytest.approx(100 / total_steps, rel=1)
        assert data["correct_responses"] == 0
        assert data["incorrect_responses"] == 0
        assert data["is_complete"] == False
    
    def test_get_nonexistent_session_status(self):
        """Test getting status of non-existent session"""
        response = client.get("/step-sequencing/nonexistent_session")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_progress_calculation(self):
        """Test that progress percentage is calculated correctly"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        
        # Get status
        response = client.get(f"/step-sequencing/{session_id}")
        data = response.json()
        
        # Check progress calculation: current_step / total_steps * 100
        expected_progress = (data["current_step_number"] / data["total_steps"]) * 100
        assert data["progress_percent"] == pytest.approx(expected_progress, abs=0.1)


class TestDeleteSession:
    """Tests for DELETE /step-sequencing/{session_id} endpoint"""
    
    def test_delete_session_success(self):
        """Test successful session deletion"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        
        # Verify session exists
        assert session_id in step_sequencing._sessions
        
        # Delete session
        response = client.delete(f"/step-sequencing/{session_id}")
        
        assert response.status_code == 200
        assert response.json()["message"] == f"Session {session_id} deleted"
        
        # Verify session is deleted
        assert session_id not in step_sequencing._sessions
    
    def test_delete_nonexistent_session(self):
        """Test deleting a non-existent session"""
        response = client.delete("/step-sequencing/nonexistent_session")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestIntegration:
    """Integration tests for full teaching workflow"""
    
    def test_full_teaching_workflow(self):
        """Test complete teaching workflow: start → respond → complete"""
        # 1. Start teaching
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
                "learning_style": "visual",
            }
        )
        
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        first_step = start_response.json()["current_step"]
        total_steps = start_response.json()["total_steps"]
        
        # 2. Check status
        status_response = client.get(f"/step-sequencing/{session_id}")
        assert status_response.status_code == 200
        assert status_response.json()["total_steps"] == total_steps
        
        # 3. Respond to first step
        respond_response = client.post(
            f"/step-sequencing/{session_id}/respond",
            json={
                "student_response": "test response",
                "response_type": "text",
                "confidence_level": "medium",
                "time_spent_seconds": 30,
            }
        )
        
        assert respond_response.status_code == 200
        response_data = respond_response.json()
        assert "feedback" in response_data
        assert "is_correct" in response_data
        
        # 4. Get updated status
        final_status = client.get(f"/step-sequencing/{session_id}")
        assert final_status.status_code == 200
        
        # 5. Delete session
        delete_response = client.delete(f"/step-sequencing/{session_id}")
        assert delete_response.status_code == 200
    
    def test_multiple_student_sessions(self):
        """Test that multiple students can have separate sessions"""
        # Student 1 starts session
        start1 = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session1 = start1.json()["session_id"]
        
        # Student 2 starts session with same problem
        start2 = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_002",
            }
        )
        session2 = start2.json()["session_id"]
        
        # Sessions should be different
        assert session1 != session2
        
        # Both sessions should exist in storage
        assert session1 in step_sequencing._sessions
        assert session2 in step_sequencing._sessions
        
        # Verify student IDs are correct
        assert step_sequencing._sessions[session1]["student_id"] == "student_001"
        assert step_sequencing._sessions[session2]["student_id"] == "student_002"


class TestErrorHandling:
    """Tests for error handling and edge cases"""
    
    def test_invalid_request_body(self):
        """Test handling of invalid request body"""
        response = client.post(
            "/step-sequencing/start",
            json={"invalid_field": "value"}  # Missing required fields
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_empty_student_response(self):
        """Test handling of empty student response"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        
        # Respond with empty response
        response = client.post(
            f"/step-sequencing/{session_id}/respond",
            json={
                "student_response": "",
                "response_type": "text",
            }
        )
        
        # Should still process (may be treated as incorrect)
        assert response.status_code == 200
    
    def test_very_long_student_response(self):
        """Test handling of very long student response"""
        # Start session
        start_response = client.post(
            "/step-sequencing/start",
            json={
                "problem_id": "math_linear_001",
                "student_id": "student_001",
            }
        )
        session_id = start_response.json()["session_id"]
        
        # Respond with very long response
        long_response = "a" * 10000  # 10k characters
        response = client.post(
            f"/step-sequencing/{session_id}/respond",
            json={
                "student_response": long_response,
                "response_type": "text",
            }
        )
        
        # Should still process
        assert response.status_code == 200
