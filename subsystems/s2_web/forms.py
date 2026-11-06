import math

from flask_wtf import FlaskForm
from wtforms import FloatField, IntegerField
from wtforms.validators import InputRequired, NumberRange, ValidationError


def multiple_of(step):
    def check(form, field):
        if field.data is None:
            return
        if not math.isfinite(field.data):
            raise ValidationError("Enter a number.")
        if round(field.data / step, 6) % 1 != 0:
            raise ValidationError(f"Use steps of {step:g}.")

    return check


class ScenarioForm(FlaskForm):
    heating_change = FloatField(
        "Heating change (°C)",
        default=-1.0,
        validators=[
            InputRequired("Enter a heating change."),
            multiple_of(0.5),
            NumberRange(-3, 3, "Enter a value from −3 to +3 °C."),
        ],
    )
    lighting_reduction = IntegerField(
        "Lighting reduction (%)",
        default=20,
        validators=[
            InputRequired("Enter a lighting reduction."),
            multiple_of(5),
            NumberRange(0, 50, "Enter a value from 0 to 50%%."),
        ],
    )

    @property
    def changes(self):
        """The two scenario inputs as a (heating_change, lighting_reduction) pair."""
        return self.heating_change.data, self.lighting_reduction.data

    @changes.setter
    def changes(self, pair):
        heating, lighting = pair
        self.heating_change.data = heating
        self.lighting_reduction.data = lighting


def limit_field(label):
    return FloatField(
        label,
        validators=[
            InputRequired(f"Enter a limit for {label.lower()}."),
            multiple_of(0.1),
            NumberRange(0.1, 20, "Enter a value from 0.1 to 20 kWh/h."),
        ],
    )


class ThresholdForm(FlaskForm):
    heating = limit_field("Heating")
    lighting = limit_field("Lighting")
    servers = limit_field("Servers")
    other = limit_field("Other")

    @property
    def limits(self):
        """Alert limits keyed by device type, in kWh per hour."""
        return {name: self[name].data for name in ("heating", "lighting", "servers", "other")}

    @limits.setter
    def limits(self, values):
        for name in ("heating", "lighting", "servers", "other"):
            if name not in values:
                raise ValueError(f"Missing limit for '{name}'.")
            self[name].data = values[name]
