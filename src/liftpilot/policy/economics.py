"""Campaign economics: from uplift to incremental profit.

Notation for one customer ``i``:

=========  ==================================================================
``V_i``    expected revenue of one purchase in the campaign window (basket)
``m``      gross margin rate (share of revenue kept after cost of goods)
``c``      cost of sending one message
``d``      incentive depth: share of the basket given away as a discount to a
           contacted customer who buys (0 for a pure reminder)
``p0_i``   probability of buying if NOT contacted
``p1_i``   probability of buying if contacted
``tau_i``  uplift = ``p1_i - p0_i``
=========  ==================================================================

Expected profit if contacted      = ``(m - d) V_i p1_i - c``
Expected profit if left alone     = ``m V_i p0_i``
Incremental profit of contacting  = ``g_i = m V_i tau_i - d V_i p1_i - c``

So contacting pays only when ``tau_i`` exceeds the *break-even uplift*

    tau*_i = (c + d V_i p1_i) / (m V_i)

The discount term is what makes "sure things" expensive: they buy anyway
(``tau`` near 0) but still collect the discount (``p1`` high).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field, model_validator

FloatArray = NDArray[np.float64]


class Economics(BaseModel):
    """Money assumptions of one campaign. All amounts in ``currency``."""

    margin: float = Field(0.25, gt=0, le=1, description="gross margin rate m")
    contact_cost: float = Field(2.0, ge=0, description="cost per message c")
    discount: float = Field(0.0, ge=0, lt=1, description="incentive depth d (share of basket)")
    currency: str = "RUB"

    @model_validator(mode="after")
    def _discount_below_margin(self) -> Economics:
        if self.discount >= self.margin:
            raise ValueError("discount must be smaller than margin, or every sale loses money")
        return self

    @property
    def break_even_roas(self) -> float:
        """Revenue needed per unit of spend just to cover it (course rule: 1 / margin)."""
        return 1.0 / self.margin


def _arr(x: Any) -> FloatArray:
    return np.asarray(x, dtype=np.float64).ravel()


def expected_spend(econ: Economics, value: Any, p1: Any) -> FloatArray:
    """Expected cash out for contacting each customer: message + expected discount."""
    return econ.contact_cost + econ.discount * _arr(value) * _arr(p1)


def incremental_profit(econ: Economics, value: Any, uplift: Any, p1: Any) -> FloatArray:
    """Expected incremental profit ``g_i`` of contacting each customer."""
    v = _arr(value)
    return econ.margin * v * _arr(uplift) - econ.discount * v * _arr(p1) - econ.contact_cost


def break_even_uplift(econ: Economics, value: Any, p1: Any) -> FloatArray:
    """Minimum uplift at which contacting a customer stops losing money."""
    v = np.maximum(_arr(value), 1e-9)
    return (econ.contact_cost + econ.discount * v * _arr(p1)) / (econ.margin * v)


def realised_profit(econ: Economics, revenue: Any, treated: Any) -> FloatArray:
    """Profit actually observed for each customer in an experiment.

    ``revenue`` is the observed revenue in the outcome window (0 for non-buyers).
    Treated customers cost a message and, if they bought, a discount.
    """
    rev = _arr(revenue)
    t = _arr(treated)
    profit_treated = (econ.margin - econ.discount) * rev - econ.contact_cost
    profit_control = econ.margin * rev
    return np.where(t == 1, profit_treated, profit_control)
