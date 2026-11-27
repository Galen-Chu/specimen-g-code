"""Third domain: an Unbodysoma behaviour run — the endogenous specimen.

Raw inputs are one ``signals.csv`` (the ~95-channel time series a run
samples) plus its ``meta.json`` (generator version, scenario identity, the
scenario TOML it ran). The recipe emits one ``signals`` table (grain
``signal``, one row per recorded time step): every channel the run served,
plus the run identity columns derived from meta.json.

The time axis is simulated seconds — an integer-ordered split (ADR-0001 as
amended) applies: train through 200 s, valid (200, 250], test beyond.
Assay is deferred until a learning question exists for behaviour (the
intended one — predicting next action from physiological state — belongs to
Unbodysoma's Phase 3 learning mind; this specimen is its training corpus).

Declared rules (none implicit):

- time_seconds: the ``time`` column is whole seconds (sample cadence is
  whole-second); float forms are normalised to ints.
- drop_incomplete: the t=0 row precedes the first simulation step and
  carries blanks in most channels — incomplete rows are dropped, never
  zero-filled (the case study's fillna(0) antonym).
- run_identity: every row carries the scenario name and generator version
  parsed from meta.json.
- sort_by_time: rows sorted by time; times must be unique after
  normalisation (duplicate timestamps are a refusal).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping

from ..manifest import ColumnSpec, Splits, TableContract

STEPS = (
    "parse_meta",
    "parse_signals_csv",
    "time_seconds",
    "drop_incomplete",
    "run_identity",
    "sort_by_time",
)
INPUTS = ("signals.csv", "meta.json")
SPLITS = Splits(method="integer-ordered", train_end="200", valid_end="250")

# The pinned run's 100-channel header, embedded as the contract (the fixture
# is registry-pinned, so this header is stable). Channels carry no range
# limits in v1: several are signed (circadian, valence) and the physiological
# envelopes are not yet documented; types and availability are the v1
# contract. Embedded as a constant — importing the installed package must not
# reach for a fixture file.
SIGNAL_HEADER: tuple[str, ...] = (
    "time",
    "extero.food",
    "extero.in_shelter",
    "extero.shelter_known",
    "extero.threat",
    "extero.water",
    "intero.cardiac_arousal",
    "intero.circadian",
    "intero.energy_deficit",
    "intero.pain",
    "intero.sleep_pressure",
    "intero.thermal",
    "intero.water_deficit",
    "motor.drinking",
    "motor.eating",
    "motor.exertion",
    "motor.sleeping",
    "neuro.dopamine",
    "neuro.norepinephrine",
    "neuro.relief",
    "neuro.serotonin",
    "psyche.action.p_drink",
    "psyche.action.p_eat",
    "psyche.action.p_explore",
    "psyche.action.p_flee",
    "psyche.action.p_idle",
    "psyche.action.p_seek_shelter",
    "psyche.action.p_seek_water",
    "psyche.action.p_sleep",
    "psyche.action.selected_drink",
    "psyche.action.selected_eat",
    "psyche.action.selected_explore",
    "psyche.action.selected_flee",
    "psyche.action.selected_idle",
    "psyche.action.selected_seek_shelter",
    "psyche.action.selected_seek_water",
    "psyche.action.selected_sleep",
    "psyche.affect.arousal",
    "psyche.affect.valence",
    "psyche.anticipation.hunger",
    "psyche.anticipation.threat",
    "psyche.appraisal.threat",
    "psyche.attention.focus_share",
    "psyche.attention.share_hunger",
    "psyche.attention.share_pain",
    "psyche.attention.share_sleepiness",
    "psyche.attention.share_thermal",
    "psyche.attention.share_thirst",
    "psyche.attention.share_threat",
    "psyche.conditioning.defense_a",
    "psyche.conditioning.defense_b",
    "psyche.conditioning.reward_prediction",
    "psyche.conditioning.threat_expectation",
    "psyche.drive.hunger",
    "psyche.drive.sleepiness",
    "psyche.drive.thermal_discomfort",
    "psyche.drive.thirst",
    "psyche.habituation.novelty",
    "psyche.instrumental.value_drink",
    "psyche.instrumental.value_eat",
    "psyche.instrumental.value_explore",
    "psyche.instrumental.value_flee",
    "psyche.instrumental.value_idle",
    "psyche.instrumental.value_seek_shelter",
    "psyche.instrumental.value_seek_water",
    "psyche.instrumental.value_sleep",
    "psyche.memory.episodes",
    "psyche.memory.mood_congruence",
    "soma.cardio.heart_rate",
    "soma.circadian.clock_hour",
    "soma.circadian.drive",
    "soma.endocrine.adrenaline",
    "soma.endocrine.cortisol",
    "soma.fluid.hydration",
    "soma.fluid.osmolality",
    "soma.metabolism.energy_reserve",
    "soma.metabolism.glucose",
    "soma.metabolism.insulin",
    "soma.nociception.burning",
    "soma.nociception.injury",
    "soma.nociception.pain",
    "soma.nociception.sharp",
    "soma.respiration.minute_ventilation",
    "soma.respiration.rate",
    "soma.respiration.spo2",
    "soma.sleep.pressure",
    "soma.thermo.core_temperature",
    "soma.thermo.shivering",
    "soma.thermo.sweating",
    "world.ambient_temperature",
    "world.damage",
    "world.food_available",
    "world.food_intake",
    "world.in_shelter",
    "world.shelter_known",
    "world.stimulus",
    "world.stimulus_b",
    "world.threat",
    "world.water_available",
    "world.water_intake",
)


def _contract() -> TableContract:
    columns = tuple(
        ColumnSpec(
            name,
            "int" if name == "time" else "float",
            availability_lag_days=0.0,  # endogenous: knowable with the row itself
        )
        for name in SIGNAL_HEADER
    )
    return TableContract(name="signals", grain="signal", key=("time",), columns=columns)


CONTRACTS = (_contract(),)


def run(seed: int, inputs: Mapping[str, bytes]) -> dict[str, str]:
    meta = json.loads(inputs["meta.json"].decode("utf-8"))
    scenario_name = str(meta["config"]["scenario"])
    generator_version = str(meta["unbodysoma_version"]) if "unbodysoma_version" in meta else str(meta["unbodysoma"])

    reader = csv.DictReader(io.StringIO(inputs["signals.csv"].decode("utf-8")))
    header = tuple(reader.fieldnames or [])
    rows: list[dict[str, str]] = []
    seen_times: set[int] = set()
    for row in reader:
        # time_seconds: whole seconds; drop_incomplete: blanks are refused,
        # not filled (the t=0 row precedes the first simulation step).
        if any(value == "" or value is None for value in row.values()):
            continue
        seconds = float(row["time"])
        if not seconds.is_integer():
            raise ValueError(f"time_seconds: {row['time']!r} is not a whole second")
        seconds_int = int(seconds)
        if seconds_int in seen_times:  # declared refusal: duplicate timestamps
            raise ValueError(f"time_seconds: duplicate timestamp {seconds_int}")
        seen_times.add(seconds_int)
        rows.append(
            {
                **{name: row[name] for name in header if name != "time"},
                "time": str(seconds_int),
                "scenario": scenario_name,
                "generator_version": generator_version,
            }
        )

    rows.sort(key=lambda r: int(r["time"]))  # sort_by_time

    out_header = (
        ("time",)
        + tuple(name for name in header if name != "time")
        + (
            "scenario",
            "generator_version",
        )
    )
    return {"signals": _to_csv(out_header, rows)}


def _to_csv(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in header})
    return buffer.getvalue()
