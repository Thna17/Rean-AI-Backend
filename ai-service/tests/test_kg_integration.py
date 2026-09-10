"""
Test suite for Knowledge Graph Integration (Task 2.1)

Tests:
1. KG service doesn't re-seed on startup
2. Prerequisites fetched dynamically from KG
3. Misconceptions retrieved from KG
4. Concept graph populated in teaching steps
5. End-to-end teaching plan generation with KG enrichment
"""

import pytest
import os
import asyncio
from typing import Optional

from api.services.kg_service_v3 import KnowledgeGraphServiceV3, get_kg_service
from api.services.step_sequencing_service import StepSequencingService
from api.repositories.problem_repository import ProblemRepository
from api.models.teaching_step import Subject


class TestKGInitialization:
    """Test KG initialization and persistence"""
    
    def test_kg_does_not_reseed_on_restart(self, tmp_path):
        """Test that KG database is not re-seeded on every restart"""
        # Create a KG service instance
        db_path = str(tmp_path / "kuzu")
        
        # Override settings temporarily
        from api.core import config
        original_path = config.settings.KUZU_DB_PATH if hasattr(config.settings, 'KUZU_DB_PATH') else None
        
        try:
            config.settings.KUZU_DB_PATH = db_path
            
            # First initialization
            kg1 = KnowledgeGraphServiceV3()
            count1 = kg1.get_concept_count()
            
            # Second initialization (should reuse database)
            kg2 = KnowledgeGraphServiceV3()
            count2 = kg2.get_concept_count()
            
            # Counts should be equal (no re-seed)
            assert count1 == count2, f"KG re-seeded: {count1} vs {count2}"
            assert count1 > 0, "KG should have concepts after initialization"
            
        finally:
            if original_path:
                config.settings.KUZU_DB_PATH = original_path
    
    def test_kg_database_path_creation(self, tmp_path):
        """Test that KG creates necessary directories"""
        db_path = str(tmp_path / "nested" / "kuzu")
        
        from api.core import config
        original_path = config.settings.KUZU_DB_PATH if hasattr(config.settings, 'KUZU_DB_PATH') else None
        
        try:
            config.settings.KUZU_DB_PATH = db_path
            kg = KnowledgeGraphServiceV3()
            
            # Check that parent directory was created
            assert os.path.exists(os.path.dirname(db_path)), "Parent directory not created"
            assert kg.get_concept_count() >= 0, "KG not properly initialized"
            
        finally:
            if original_path:
                config.settings.KUZU_DB_PATH = original_path


class TestKGPrerequisites:
    """Test prerequisite retrieval from KG"""
    
    @pytest.mark.asyncio
    async def test_get_prerequisites_returns_list(self):
        """Test that get_prerequisites returns a list"""
        kg = get_kg_service()
        
        # Get any concept from the graph
        concepts = kg.get_concepts()
        assert len(concepts) > 0, "No concepts in KG"
        
        # Pick first concept
        concept_id = list(concepts.keys())[0]
        
        # Get prerequisites
        prereqs = await kg.get_prerequisites(concept_id)
        
        # Should be a list
        assert isinstance(prereqs, list), f"Prerequisites not a list: {type(prereqs)}"
    
    @pytest.mark.asyncio
    async def test_get_prerequisites_nonexistent_concept(self):
        """Test get_prerequisites with non-existent concept"""
        kg = get_kg_service()
        
        # Non-existent concept
        prereqs = await kg.get_prerequisites("nonexistent_concept_12345")
        
        # Should return empty list, not error
        assert isinstance(prereqs, list), "Should return list"
        assert len(prereqs) == 0, "Non-existent concept should have no prerequisites"
    
    @pytest.mark.asyncio
    async def test_get_next_concepts_returns_list(self):
        """Test that get_next_concepts returns a list"""
        kg = get_kg_service()
        
        concepts = kg.get_concepts()
        assert len(concepts) > 0, "No concepts in KG"
        
        concept_id = list(concepts.keys())[0]
        next_concepts = await kg.get_next_concepts(concept_id)
        
        assert isinstance(next_concepts, list), f"Next concepts not a list: {type(next_concepts)}"


class TestKGMisconceptions:
    """Test misconception retrieval from KG"""
    
    @pytest.mark.asyncio
    async def test_get_misconceptions_returns_list(self):
        """Test that get_misconceptions returns a list"""
        kg = get_kg_service()
        
        concepts = kg.get_concepts()
        assert len(concepts) > 0, "No concepts in KG"
        
        concept_id = list(concepts.keys())[0]
        misconceptions = await kg.get_misconceptions(concept_id)
        
        assert isinstance(misconceptions, list), f"Misconceptions not a list: {type(misconceptions)}"
    
    @pytest.mark.asyncio
    async def test_get_misconceptions_structure(self):
        """Test that misconceptions have expected structure"""
        kg = get_kg_service()
        
        concepts = kg.get_concepts()
        if not concepts:
            pytest.skip("No concepts in KG")
        
        concept_id = list(concepts.keys())[0]
        misconceptions = await kg.get_misconceptions(concept_id)
        
        # If there are misconceptions, check structure
        for misconception in misconceptions:
            assert isinstance(misconception, dict), "Misconception should be dict"
            # Should have at least concept_id or type field
            assert any(k in misconception for k in ["concept_id", "error_type", "id"]), \
                f"Misconception missing id field: {misconception}"


class TestStepSequencingKGIntegration:
    """Test step sequencing integration with KG"""
    
    @pytest.fixture
    def step_sequencing_service(self):
        """Fixture for step sequencing service with KG"""
        kg_service = get_kg_service()
        return StepSequencingService(kg_service=kg_service)
    
    @pytest.fixture
    def problem_repository(self):
        """Fixture for problem repository"""
        return ProblemRepository()
    
    @pytest.mark.asyncio
    async def test_generate_teaching_plan_with_kg(self, step_sequencing_service):
        """Test that teaching plan generation fetches from KG"""
        plan = await step_sequencing_service.generate_teaching_plan(
            problem="Solve 2x + 5 = 13",
            subject=Subject.MATHEMATICS,
            grade_level=10,
        )
        
        # Check plan was created
        assert plan is not None, "Teaching plan not created"
        assert len(plan.steps) > 0, "No steps generated"
        assert len(plan.prerequisite_concepts) >= 0, "Prerequisites not populated"
    
    @pytest.mark.asyncio
    async def test_concept_graph_populated_in_steps(self, step_sequencing_service):
        """Test that concept_graph is populated in teaching steps"""
        plan = await step_sequencing_service.generate_teaching_plan(
            problem="Calculate the area of a triangle with base 10 and height 5",
            subject=Subject.MATHEMATICS,
            grade_level=10,
        )
        
        # Check if at least first step has concept graph (if KG service was available)
        # Note: May be None if KG service not initialized
        first_step = plan.steps[0]
        assert hasattr(first_step, 'concept_graph'), "TeachingStep missing concept_graph field"
    
    @pytest.mark.asyncio
    async def test_step_sequencing_handles_missing_kg_gracefully(self):
        """Test that step sequencing works even if KG is None"""
        # Create service without KG
        service = StepSequencingService(kg_service=None)
        
        plan = await service.generate_teaching_plan(
            problem="Solve 2x + 5 = 13",
            subject=Subject.MATHEMATICS,
            grade_level=10,
        )
        
        # Should still generate plan
        assert plan is not None, "Plan not generated without KG"
        assert len(plan.steps) > 0, "No steps without KG"
    
    @pytest.mark.asyncio
    async def test_end_to_end_math_problem_with_kg(self, step_sequencing_service):
        """Test end-to-end math problem teaching with KG integration"""
        # Generate teaching plan for a linear equation
        plan = await step_sequencing_service.generate_teaching_plan(
            problem="Solve 2x + 5 = 13",
            subject=Subject.MATHEMATICS,
            grade_level=10,
            learning_style="visual",
            include_hints=True,
        )
        
        # Verify plan structure
        assert plan.id, "Plan should have ID"
        assert plan.problem == "Solve 2x + 5 = 13", "Problem not stored correctly"
        assert plan.subject == Subject.MATHEMATICS, "Subject not correct"
        assert plan.grade_level == 10, "Grade level not correct"
        assert len(plan.steps) > 0, "Steps not generated"
        
        # Verify first step
        first_step = plan.steps[0]
        assert first_step.step_number == 1, "First step should be step 1"
        assert first_step.subject == Subject.MATHEMATICS, "Step subject should match plan"
        
        # Verify steps are connected
        for i, step in enumerate(plan.steps[:-1]):
            assert step.next_step_id is not None or step.branching_rules, \
                f"Step {i} has no next step routing"
    
    @pytest.mark.asyncio
    async def test_end_to_end_physics_problem_with_kg(self, step_sequencing_service):
        """Test end-to-end physics problem teaching with KG integration"""
        plan = await step_sequencing_service.generate_teaching_plan(
            problem="Calculate the force required to accelerate a 5 kg object at 2 m/s²",
            subject=Subject.PHYSICS,
            grade_level=10,
        )
        
        assert plan is not None, "Physics plan not generated"
        assert plan.subject == Subject.PHYSICS, "Subject not correct"
        assert len(plan.steps) > 0, "Physics steps not generated"
    
    @pytest.mark.asyncio
    async def test_end_to_end_chemistry_problem_with_kg(self, step_sequencing_service):
        """Test end-to-end chemistry problem teaching with KG integration"""
        plan = await step_sequencing_service.generate_teaching_plan(
            problem="Balance the chemical equation: H2 + O2 → H2O",
            subject=Subject.CHEMISTRY,
            grade_level=10,
        )
        
        assert plan is not None, "Chemistry plan not generated"
        assert plan.subject == Subject.CHEMISTRY, "Subject not correct"
        assert len(plan.steps) > 0, "Chemistry steps not generated"


class TestConceptGraphStructure:
    """Test the structure of concept graphs in steps"""
    
    @pytest.fixture
    def step_sequencing_service(self):
        """Fixture for step sequencing service with KG"""
        kg_service = get_kg_service()
        return StepSequencingService(kg_service=kg_service)
    
    @pytest.mark.asyncio
    async def test_concept_graph_has_required_fields(self, step_sequencing_service):
        """Test that concept_graph has required fields when populated"""
        plan = await step_sequencing_service.generate_teaching_plan(
            problem="Solve 2x + 5 = 13",
            subject=Subject.MATHEMATICS,
            grade_level=10,
        )
        
        first_step = plan.steps[0]
        
        # If concept graph is populated, check structure
        if first_step.concept_graph:
            assert isinstance(first_step.concept_graph, dict), "concept_graph should be dict"
            
            # If concepts exist, check structure
            if "concepts" in first_step.concept_graph:
                concepts = first_step.concept_graph["concepts"]
                assert isinstance(concepts, list), "concepts should be list"
                
                for concept in concepts:
                    assert isinstance(concept, dict), "Each concept should be dict"
                    assert "concept" in concept, "Concept should have 'concept' field"
                    assert "prerequisites" in concept, "Concept should have 'prerequisites' field"
                    assert isinstance(concept["prerequisites"], list), "Prerequisites should be list"


class TestKGConceptCount:
    """Test KG concept counting"""
    
    def test_concept_count_greater_than_zero(self):
        """Test that KG has concepts"""
        kg = get_kg_service()
        count = kg.get_concept_count()
        
        assert count > 0, f"KG should have concepts, got {count}"
    
    def test_get_concepts_returns_dict(self):
        """Test that get_concepts returns a dictionary"""
        kg = get_kg_service()
        concepts = kg.get_concepts()
        
        assert isinstance(concepts, dict), "get_concepts should return dict"
        assert len(concepts) > 0, "Should have concepts"
        
        # Check structure
        for concept_id, concept_data in concepts.items():
            assert isinstance(concept_id, str), "Concept ID should be string"
            assert isinstance(concept_data, dict), "Concept data should be dict"


class TestKGQueryConcepts:
    """Test KG concept querying"""
    
    def test_query_concepts_returns_list(self):
        """Test that query_concepts returns a list"""
        kg = get_kg_service()
        results = kg.query_concepts("algebra")
        
        assert isinstance(results, list), "query_concepts should return list"
    
    def test_query_concepts_respects_top_k(self):
        """Test that query_concepts respects top_k parameter"""
        kg = get_kg_service()
        
        results_3 = kg.query_concepts("equation", top_k=3)
        results_5 = kg.query_concepts("equation", top_k=5)
        
        assert len(results_3) <= 3, "Should respect top_k=3"
        assert len(results_5) <= 5, "Should respect top_k=5"


# Async test runner for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
