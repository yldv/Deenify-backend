from django.urls import path

from .views import (
    QuizAnswerView,
    QuizNextQuestionView,
    QuizProgressView,
    QuizResetView,
    QuizRestartView,
)

urlpatterns = [
    path("api/v1/quiz/progress/", QuizProgressView.as_view(), name="quiz-progress"),
    path("api/v1/quiz/next/", QuizNextQuestionView.as_view(), name="quiz-next"),
    path("api/v1/quiz/answer/", QuizAnswerView.as_view(), name="quiz-answer"),
    path("api/v1/quiz/restart/", QuizRestartView.as_view(), name="quiz-restart"),
    path("api/v1/quiz/reset/", QuizResetView.as_view(), name="quiz-reset"),
]
