class AuditError(RuntimeError):
    """Ошибка шага аудита с сообщением, которое можно показать пользователю.

    retryable=True: ошибка временная (сеть, лимиты), задачу стоит повторить.
    retry_after: сколько секунд просит подождать внешний сервис, если он это сообщил.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
