import random

from rest_framework import serializers

from .models import Answer, Test
from .services.quiz_content import resolve_localized_text


class BotQuizAnswerSerializer(serializers.ModelSerializer):
    text = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ("id", "text")

    def get_text(self, obj):
        return resolve_localized_text(obj, "text")


class BotQuizQuestionSerializer(serializers.ModelSerializer):
    answers = BotQuizAnswerSerializer(many=True, read_only=True)
    question = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    correct_option_index = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = ("id", "question", "answers", "description", "correct_option_index")

    def get_question(self, obj):
        return resolve_localized_text(obj, "question")

    def get_description(self, obj):
        return resolve_localized_text(obj, "description")

    def get_correct_option_index(self, obj):
        for index, answer in enumerate(obj.answers.all()):
            if answer.is_correct:
                return index
        return 0

    def to_representation(self, instance):
        data = super().to_representation(instance)
        answers = [
            item for item in data.get("answers", [])
            if (item.get("text") or "").strip()
        ]
        if len(answers) < 2:
            data["answers"] = answers
            return data

        correct_id = next(
            (answer.id for answer in instance.answers.all() if answer.is_correct),
            None,
        )
        random.shuffle(answers)
        data["answers"] = answers
        if correct_id is not None:
            data["correct_option_index"] = next(
                (index for index, item in enumerate(answers) if item["id"] == correct_id),
                0,
            )
        return data


class QuizTelegramIdSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()


class QuizAnswerSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    test_id = serializers.IntegerField()
    answer_id = serializers.IntegerField()


class QuizRestartSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
