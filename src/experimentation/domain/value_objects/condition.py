from enum import Enum


class Condition(str, Enum):
    """Bajo qué condición se resuelve un lote.

    Misma interfaz en las dos. La de control oculta veredicto, confianza,
    justificación y sello, y no reordena. Así la diferencia que se mide es el
    asistente y no el aspecto de la pantalla.
    """

    WITH_ASSISTANT = "con_asistente"
    CONTROL = "sin_asistente"

    @property
    def shows_verdict(self) -> bool:
        return self is Condition.WITH_ASSISTANT

    @property
    def orders_by_priority(self) -> bool:
        return self is Condition.WITH_ASSISTANT

    @property
    def opposite(self) -> "Condition":
        return (
            Condition.CONTROL
            if self is Condition.WITH_ASSISTANT
            else Condition.WITH_ASSISTANT
        )


# La decisión se mudó a `finding_validation` cuando se vio que el acto es del
# producto y no del estudio. Aquí quedaba una copia con los mismos tres
# valores, y eso no era inocuo: una decisión construida con esta enumeración
# no era «la misma» que la de allá, de modo que `is_correct_against` comparaba
# contra otro objeto y daba por errado lo acertado. Se reexporta la de verdad.
from ....finding_validation.domain.entities.decision import (  # noqa: E402
    DecisionValue,
)

__all__ = ["Condition", "DecisionValue"]
