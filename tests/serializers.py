import random

from rest_framework import serializers

from .models import Answer, Test


class BotQuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ("id", "text")


class BotQuizQuestionSerializer(serializers.ModelSerializer):
    answers = BotQuizAnswerSerializer(many=True, read_only=True)
    description = serializers.CharField(read_only=True)
    explanation = serializers.CharField(read_only=True)
    correct_option_index = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = ("id", "question", "answers", "description", "explanation", "correct_option_index")

    def get_correct_option_index(self, obj):
        for index, answer in enumerate(obj.answers.all()):
            if answer.is_correct:
                return index
        return 0

    def to_representation(self, instance):
        data = super().to_representation(instance)
        answers = list(data.get("answers", []))
        if len(answers) < 2:
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
