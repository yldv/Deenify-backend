class PaymentRequired(Exception):
    pass


class QuizCompleted(Exception):
    """All questions in the current round are answered."""
