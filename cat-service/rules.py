"""Regras de alarme do CAT. Sem I/O."""

SUDDEN_INCREASE = "sudden_increase"
HIGH_TEMPERATURE = "high_temperature"


class AlarmRules:
    """Decide quais eventos disparar a cada nova média.

    - sudden_increase: |média - média anterior| >= jump_threshold. Cada salto
      é um evento distinto, então dispara a cada ciclo em que ocorre.
    - high_temperature: média > high_threshold. Dispara só na transição
      (de abaixo para acima); rearma quando a média volta a <= limiar.
    """

    def __init__(self, jump_threshold, high_threshold):
        self._jump = jump_threshold
        self._high = high_threshold
        self._above_high = False

    def evaluate(self, avg, prev_avg):
        events = []
        if prev_avg is not None and abs(avg - prev_avg) >= self._jump:
            events.append(SUDDEN_INCREASE)
        is_high = avg > self._high
        if is_high and not self._above_high:
            events.append(HIGH_TEMPERATURE)
        self._above_high = is_high
        return events
