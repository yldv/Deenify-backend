from rest_framework import serializers

from .models import Answer, Test, TestCategory, UserTestSession


class TestCategorySerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(source="sort_order")

    class Meta:
        model = TestCategory
        fields = ("id", "name", "slug", "order")


class AnswerPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ("id", "text")


class TestQuestionSerializer(serializers.ModelSerializer):
    answers = AnswerPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = ("id", "question", "answers")


class StartSessionSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    test_type = serializers.ChoiceField(choices=("easy", "medium", "hard", "mixed"))


class StartSessionResponseSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    test_type = serializers.CharField()
    total_questions = serializers.IntegerField()
    questions = TestQuestionSerializer(many=True)


class SubmitAnswerSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    test_id = serializers.IntegerField()
    answer_id = serializers.IntegerField()


class FinishSessionSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()


class SessionStatsSerializer(serializers.ModelSerializer):
    score_percent = serializers.IntegerField()

    class Meta:
        model = UserTestSession
        fields = (
            "total_questions",
            "correct_answers",
            "wrong_answers",
            "score_percent",
        )
