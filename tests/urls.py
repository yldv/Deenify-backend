from django.urls import path

from .views import (
    FinishSessionView,
    StartTestSessionView,
    SubmitAnswerView,
    TestCategoryListView,
)

urlpatterns = [
    path(
        "api/v1/tests/categories/",
        TestCategoryListView.as_view(),
        name="test-category-list",
    ),
    path(
        "api/v1/tests/sessions/start/",
        StartTestSessionView.as_view(),
        name="test-session-start",
    ),
    path(
        "api/v1/tests/sessions/<int:session_id>/answer/",
        SubmitAnswerView.as_view(),
        name="test-session-answer",
    ),
    path(
        "api/v1/tests/sessions/<int:session_id>/finish/",
        FinishSessionView.as_view(),
        name="test-session-finish",
    ),
]
