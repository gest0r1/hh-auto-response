from app.learning import LearningEngine


def test_learning_increases_weights_after_positive_feedback():
    engine = LearningEngine(initial_weights={"React": 1.0})

    update = engine.learn_from_feedback(
        event_type="approved",
        vacancy_keywords=["React", "FastAPI", "Telegram"],
        rating=5,
        edited_cover_letter="Добавил акцент на CRM и Telegram-интеграции",
    )

    assert update.weights["React"] > 1.0
    assert update.weights["FastAPI"] > 1.0
    assert update.weights["Telegram"] > 1.0
    assert "CRM" in update.extracted_preferences


def test_learning_decreases_weights_after_rejection():
    engine = LearningEngine(initial_weights={"офис": 0.2, "React": 1.0})

    update = engine.learn_from_feedback(
        event_type="rejected",
        vacancy_keywords=["офис", "Bitrix"],
        rating=1,
        notes="Не хочу офис и битрикс",
    )

    assert update.weights["офис"] < 0
    assert update.weights["Bitrix"] < 0
    assert "офис" in update.negative_signals
