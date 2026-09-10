"""Durable shared-volume published curriculum store.

Deploy one publisher against an RWX durable volume. POSIX advisory locks
serialize writers across processes; atomically replaced manifests publish a
generation/checksum for deterministic replica cache invalidation.
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from api.models.curriculum import CurriculumChunk


def published_store_path() -> Path:
    return Path(os.getenv("ADMIN_PUBLISHED_CURRICULUM_PATH", "data/curriculum/admin-published.jsonl"))


class PublishedCurriculumStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or published_store_path()
        self.manifest_path = self.path.with_suffix(".manifest.json")
        self.lock_path = self.path.with_suffix(".lock")

    def load(self) -> list[CurriculumChunk]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            return [CurriculumChunk.model_validate(json.loads(line)) for line in handle if line.strip()]

    def generation(self) -> int:
        return int(self._manifest().get("generation", 0))

    def status(self) -> dict[str, Any]:
        manifest = self._manifest()
        return {"generation": int(manifest.get("generation", 0)), "versions": len(manifest.get("versions", {})), "checksum": manifest.get("checksum", "")}

    def replace_version(self, curriculum_version_id: str, chunks: list[dict[str, Any]]) -> list[CurriculumChunk]:
        parsed = [CurriculumChunk.model_validate(chunk) for chunk in chunks]
        ids = [chunk.id for chunk in parsed]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate curriculum chunk ids")
        for chunk in parsed:
            if chunk.source.metadata.get("curriculum_version_id") != curriculum_version_id or chunk.grade not in {10, 11, 12}:
                raise ValueError("Invalid published curriculum chunk")
        payload_hash = self._checksum(parsed)
        with self._exclusive_lock():
            manifest = self._manifest()
            versions = dict(manifest.get("versions", {}))
            prior = versions.get(curriculum_version_id)
            if prior:
                if prior.get("payload_hash") != payload_hash:
                    raise ValueError("Curriculum version was already published with a different payload")
                return parsed
            retained = [chunk for chunk in self.load() if chunk.source.metadata.get("curriculum_version_id") != curriculum_version_id]
            if set(ids) & {chunk.id for chunk in retained}:
                raise ValueError("Curriculum chunk id collision")
            next_chunks = retained + parsed
            versions[curriculum_version_id] = {"payload_hash": payload_hash, "chunk_ids": ids}
            self._atomic_write(self.path, next_chunks)
            self._atomic_json(self.manifest_path, {"generation": int(manifest.get("generation", 0)) + 1, "versions": versions, "checksum": self._checksum(next_chunks)})
        return parsed

    def remove_version(self, curriculum_version_id: str) -> int:
        with self._exclusive_lock():
            current = self.load()
            retained = [chunk for chunk in current if chunk.source.metadata.get("curriculum_version_id") != curriculum_version_id]
            if len(retained) == len(current):
                return 0
            manifest = self._manifest(); versions = dict(manifest.get("versions", {})); versions.pop(curriculum_version_id, None)
            self._atomic_write(self.path, retained)
            self._atomic_json(self.manifest_path, {"generation": int(manifest.get("generation", 0)) + 1, "versions": versions, "checksum": self._checksum(retained)})
        return len(current) - len(retained)

    def _manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"generation": 0, "versions": {}, "checksum": ""}
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and isinstance(data.get("versions", {}), dict) else {"generation": 0, "versions": {}, "checksum": ""}
        except (OSError, ValueError) as exc:
            raise ValueError("Published curriculum manifest is invalid") from exc

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as handle:
            try:
                import fcntl
            except ImportError as exc:
                raise RuntimeError("Durable curriculum publishing requires POSIX file locking") from exc
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _checksum(chunks: list[CurriculumChunk]) -> str:
        text = "\n".join(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for chunk in sorted(chunks, key=lambda item: item.id))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _atomic_write(self, target: Path, chunks: list[CurriculumChunk]) -> None:
        tmp = target.with_suffix(target.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)

    def _atomic_json(self, target: Path, value: dict[str, Any]) -> None:
        tmp = target.with_suffix(target.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
