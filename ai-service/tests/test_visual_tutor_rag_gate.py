"""Unit tests for rag_curriculum_gate.py.

Verifies the 3-Tier Classification Model:
  Tier 1: Verified Curriculum (STEM + matching Admin Curriculum Content)
  Tier 2: AI Generated (Unverified STEM problem without matching curriculum content)
  Tier 3: Out of Scope (Non-STEM queries rejected with polite refusal)
"""

import pytest

from api.services.visual_tutor.rag_curriculum_gate import classify_student_query


def test_tier_1_verified_limits() -> None:
    result = classify_student_query(
        "Find the limit: lim x->3 (x^2 - 9)/(x - 3)",
        grade=12,
        subject="Mathematics",
        topic="Limits",
    )
    assert result.tier == "verified"
    assert result.subject == "mathematics"
    assert "limit" in (result.topic or "").lower()
    assert result.confidence > 0.0
    assert len(result.matching_chunks) > 0


def test_tier_1_verified_limits_of_functions_topic_phrase() -> None:
    result = classify_student_query(
        "lim_{x \\to 3} \\frac{x^2 - 9}{x - 3}",
        grade=12,
        subject="Mathematics",
        topic="Limits of Functions",
    )
    assert result.tier == "verified"
    assert result.subject == "mathematics"
    assert "limit" in (result.topic or "").lower()
    assert result.confidence > 0.0
    assert len(result.matching_chunks) > 0


def test_tier_1_verified_kinematics() -> None:
    result = classify_student_query(
        "A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
        grade=12,
        subject="Physics",
        topic="Kinematics",
    )
    assert result.tier == "verified"
    assert result.subject == "physics"
    assert result.confidence > 0.0
    assert len(result.matching_chunks) > 0


def test_tier_1_verified_chemistry_stoichiometry() -> None:
    result = classify_student_query(
        "What mass of CO2 is produced from 25 g of CaCO3 in CaCO3 -> CaO + CO2?",
        grade=12,
        subject="Chemistry",
        topic="Stoichiometry",
    )
    assert result.tier == "verified"
    assert result.subject == "chemistry"
    assert result.confidence > 0.0
    assert len(result.matching_chunks) > 0


def test_tier_1_verified_khmer_kinematics() -> None:
    result = classify_student_query(
        "ឡានមួយចាប់ផ្តើមចេញពីភាពស្ងៀមស្ងាត់ (u = 0) ដោយសំទុះ a = 2 m/s^2 ក្នុងរយៈពេល t = 5 s។ រកល្បឿនចុងក្រោយ v?",
        grade=12,
        subject="Physics",
        topic="Kinematics",
    )
    assert result.tier == "verified"
    assert result.subject == "physics"
    assert result.is_khmer is True
    assert len(result.matching_chunks) > 0


def test_tier_2_unverified_physics_projectile() -> None:
    result = classify_student_query(
        "A cannonball is launched at 45 degrees with velocity 50 m/s. Find horizontal range.",
        grade=12,
        subject="Physics",
        topic="Projectile Motion",
    )
    assert result.tier == "unverified"
    assert result.subject == "physics"


def test_tier_2_unverified_math_quadratic() -> None:
    result = classify_student_query(
        "Solve the quadratic equation x^2 - 5x + 6 = 0.",
        grade=12,
        subject="Mathematics",
    )
    assert result.tier == "unverified"
    assert result.subject == "mathematics"


def test_tier_2_unverified_chemistry_bonding() -> None:
    result = classify_student_query(
        "What is the hybridisation of carbon in ethylene (C2H4)?",
        grade=12,
        subject="Chemistry",
    )
    assert result.tier == "unverified"
    assert result.subject == "chemistry"


def test_tier_3_out_of_scope_history() -> None:
    result = classify_student_query(
        "Who was King Jayavarman VII and what did he build in Angkor?",
        grade=12,
        subject="General",
    )
    assert result.tier == "out_of_scope"
    assert result.refusal_message_en is not None
    assert "Grade 10–12" in result.refusal_message_en


def test_tier_3_out_of_scope_coding() -> None:
    result = classify_student_query(
        "Write a Python script to scrape a website using beautifulsoup.",
        grade=12,
        subject="General",
    )
    assert result.tier == "out_of_scope"


def test_tier_3_out_of_scope_cooking() -> None:
    result = classify_student_query(
        "How do I bake a chocolate cake?",
        grade=12,
        subject="General",
    )
    assert result.tier == "out_of_scope"


def test_tier_3_out_of_scope_khmer_general() -> None:
    result = classify_student_query(
        "តើនរណាជាប្រធានាធិបតីសហរដ្ឋអាមេរិក?",
        grade=12,
        subject="General",
    )
    assert result.tier == "out_of_scope"
    assert result.is_khmer is True
    assert result.refusal_message_km is not None
    assert "ថ្នាក់ទី១០-១២" in result.refusal_message_km
