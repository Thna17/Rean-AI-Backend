#!/usr/bin/env python3
"""
Phase 0.4 Validation Script

Validates that all Phase 0.4 components are correctly implemented and integrated.
"""

import sys
import os

# Add ai-service to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai-service'))

def validate_imports():
    """Validate that all Phase 0.4 modules can be imported"""
    print("=" * 70)
    print("PHASE 0.4 VALIDATION - Import Check")
    print("=" * 70)
    
    checks = [
        ("Subject Expert Models", "api.models.subject_expert_models", [
            "MathProblemType",
            "MathProblemAnalysis",
            "MathMisconception",
            "PhysicsProblemType",
            "PhysicsProblemAnalysis",
            "PhysicsMisconception",
            "ChemistryProblemType",
            "ChemistryProblemAnalysis",
            "ChemistryMisconception",
        ]),
        ("Math Expert Service", "api.services.math_expert_service", [
            "MathExpertService",
        ]),
        ("Physics Expert Service", "api.services.physics_expert_service", [
            "PhysicsExpertService",
        ]),
        ("Chemistry Expert Service", "api.services.chemistry_expert_service", [
            "ChemistryExpertService",
        ]),
        ("Teaching Step Models", "api.models.teaching_step", [
            "TeachingStep",
            "TeachingPlan",
            "EvaluationResult",
            "StepType",
            "Subject",
        ]),
    ]
    
    all_passed = True
    
    for name, module_name, items in checks:
        print(f"\n✓ Checking {name} ({module_name})")
        try:
            module = __import__(module_name, fromlist=items)
            for item in items:
                if not hasattr(module, item):
                    print(f"  ✗ Missing: {item}")
                    all_passed = False
                else:
                    print(f"  ✓ {item}")
        except ImportError as e:
            print(f"  ✗ Import failed: {e}")
            all_passed = False
    
    return all_passed


def validate_expert_services():
    """Validate that expert services have required methods"""
    print("\n" + "=" * 70)
    print("PHASE 0.4 VALIDATION - Expert Services API")
    print("=" * 70)
    
    from api.services.math_expert_service import MathExpertService
    from api.services.physics_expert_service import PhysicsExpertService
    from api.services.chemistry_expert_service import ChemistryExpertService
    
    required_methods = [
        "analyze_problem",
        "generate_steps",
        "create_visualization",
        "evaluate_response",
        "detect_misconception",
    ]
    
    experts = [
        ("MathExpertService", MathExpertService),
        ("PhysicsExpertService", PhysicsExpertService),
        ("ChemistryExpertService", ChemistryExpertService),
    ]
    
    all_passed = True
    
    for expert_name, expert_class in experts:
        print(f"\n✓ Checking {expert_name}")
        expert = expert_class()
        for method in required_methods:
            if not hasattr(expert, method):
                print(f"  ✗ Missing method: {method}")
                all_passed = False
            else:
                print(f"  ✓ {method}")
    
    return all_passed


def validate_step_sequencing_integration():
    """Validate that StepSequencingService has expert integration"""
    print("\n" + "=" * 70)
    print("PHASE 0.4 VALIDATION - Integration Check")
    print("=" * 70)
    
    from api.services.step_sequencing_service import StepSequencingService
    
    print("\n✓ Checking StepSequencingService integration")
    service = StepSequencingService()
    
    integration_checks = [
        ("math_expert", "MathExpertService"),
        ("physics_expert", "PhysicsExpertService"),
        ("chemistry_expert", "ChemistryExpertService"),
    ]
    
    all_passed = True
    
    for attr, expected_type in integration_checks:
        if not hasattr(service, attr):
            print(f"  ✗ Missing attribute: {attr}")
            all_passed = False
        else:
            expert = getattr(service, attr)
            if expert is None:
                print(f"  ✗ {attr} is None")
                all_passed = False
            else:
                print(f"  ✓ {attr} initialized ({expected_type})")
    
    return all_passed


def validate_problem_types():
    """Validate that all problem types are defined"""
    print("\n" + "=" * 70)
    print("PHASE 0.4 VALIDATION - Problem Types")
    print("=" * 70)
    
    from api.models.subject_expert_models import (
        MathProblemType,
        PhysicsProblemType,
        ChemistryProblemType,
    )
    
    math_types = [t.value for t in MathProblemType]
    physics_types = [t.value for t in PhysicsProblemType]
    chemistry_types = [t.value for t in ChemistryProblemType]
    
    print(f"\n✓ Math problem types: {len(math_types)} types")
    for t in math_types:
        print(f"    - {t}")
    
    print(f"\n✓ Physics problem types: {len(physics_types)} types")
    for t in physics_types:
        print(f"    - {t}")
    
    print(f"\n✓ Chemistry problem types: {len(chemistry_types)} types")
    for t in chemistry_types:
        print(f"    - {t}")
    
    all_passed = len(math_types) >= 10 and len(physics_types) >= 7 and len(chemistry_types) >= 6
    
    if all_passed:
        print(f"\n✓ All problem types defined (23 total)")
    else:
        print(f"\n✗ Not enough problem types defined")
    
    return all_passed


def main():
    """Run all validation checks"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " PHASE 0.4 - SUBJECT EXPERT SERVICES VALIDATION ".center(68) + "║")
    print("╚" + "=" * 68 + "╝")
    
    checks = [
        ("Import Validation", validate_imports),
        ("Expert Services API", validate_expert_services),
        ("StepSequencing Integration", validate_step_sequencing_integration),
        ("Problem Types Definition", validate_problem_types),
    ]
    
    results = []
    
    for check_name, check_fn in checks:
        try:
            result = check_fn()
            results.append((check_name, result))
        except Exception as e:
            print(f"\n✗ Error in {check_name}: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for check_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Phase 0.4 is ready!")
        print("=" * 70)
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Review errors above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
