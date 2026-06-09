#!/usr/bin/env python3
"""Generate parametric LED panel back brackets as STL and STEP files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SharedConfig:
    panel_width_mm: float
    panel_height_mm: float
    panel_gap_x_mm: float
    panel_gap_y_mm: float
    bracket_thickness_mm: float
    arm_width_mm: float
    screw_clearance_diameter_mm: float
    screw_head_diameter_mm: float
    counterbore_depth_mm: float
    edge_roundover_mm: float
    minimum_wall_mm: float
    hole_offset_x_from_panel_edge_mm: float
    hole_offset_y_from_panel_edge_mm: float


@dataclass(frozen=True)
class CrossConfig:
    arm_extension_past_hole_mm: float
    center_relief_diameter_mm: float
    screw_pair_spacing_mm: float


@dataclass(frozen=True)
class ColumnConfig:
    plate_width_mm: float
    plate_height_mm: float
    plate_hole_spacing_mm: float
    plate_hole_offset_y_mm: float
    post_width_mm: float
    post_height_mm: float
    post_depth_mm: float
    post_offset_y_mm: float


@dataclass(frozen=True)
class BracketConfig:
    shared: SharedConfig
    cross: CrossConfig
    column: ColumnConfig


class BracketConfigLoader:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> BracketConfig:
        with self.config_path.open("r", encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file) or {}

        shared = self._build_dataclass(SharedConfig, raw.get("shared", {}), "shared")
        cross = self._build_dataclass(CrossConfig, raw.get("cross", {}), "cross")
        column = self._build_dataclass(ColumnConfig, raw.get("column", {}), "column")
        config = BracketConfig(shared=shared, cross=cross, column=column)
        BracketConfigValidator(config).validate()
        return config

    @staticmethod
    def _build_dataclass(model_type: type, values: dict[str, Any], section: str) -> Any:
        expected = set(model_type.__dataclass_fields__)
        missing = sorted(expected - set(values))
        extra = sorted(set(values) - expected)
        if missing:
            raise ConfigError(f"Missing {section} config keys: {', '.join(missing)}")
        if extra:
            raise ConfigError(f"Unknown {section} config keys: {', '.join(extra)}")
        try:
            return model_type(**values)
        except TypeError as exc:
            raise ConfigError(f"Invalid {section} config: {exc}") from exc


class BracketConfigValidator:
    def __init__(self, config: BracketConfig) -> None:
        self.config = config

    def validate(self) -> None:
        shared = self.config.shared
        positive_values = {
            "panel_width_mm": shared.panel_width_mm,
            "panel_height_mm": shared.panel_height_mm,
            "bracket_thickness_mm": shared.bracket_thickness_mm,
            "arm_width_mm": shared.arm_width_mm,
            "screw_clearance_diameter_mm": shared.screw_clearance_diameter_mm,
            "minimum_wall_mm": shared.minimum_wall_mm,
            "hole_offset_x_from_panel_edge_mm": shared.hole_offset_x_from_panel_edge_mm,
            "hole_offset_y_from_panel_edge_mm": shared.hole_offset_y_from_panel_edge_mm,
            "cross.arm_extension_past_hole_mm": self.config.cross.arm_extension_past_hole_mm,
            "cross.screw_pair_spacing_mm": self.config.cross.screw_pair_spacing_mm,
            "column.plate_width_mm": self.config.column.plate_width_mm,
            "column.plate_height_mm": self.config.column.plate_height_mm,
            "column.plate_hole_spacing_mm": self.config.column.plate_hole_spacing_mm,
            "column.plate_hole_offset_y_mm": self.config.column.plate_hole_offset_y_mm,
            "column.post_width_mm": self.config.column.post_width_mm,
            "column.post_height_mm": self.config.column.post_height_mm,
            "column.post_depth_mm": self.config.column.post_depth_mm,
        }
        for name, value in positive_values.items():
            if value <= 0:
                raise ConfigError(f"{name} must be positive")

        if shared.counterbore_depth_mm < 0:
            raise ConfigError("counterbore_depth_mm must be zero or positive")
        if shared.counterbore_depth_mm >= shared.bracket_thickness_mm:
            raise ConfigError("counterbore_depth_mm must be less than bracket_thickness_mm")
        if shared.edge_roundover_mm < 0:
            raise ConfigError("edge_roundover_mm must be zero or positive")
        if shared.screw_head_diameter_mm < shared.screw_clearance_diameter_mm:
            raise ConfigError("screw_head_diameter_mm must be >= screw_clearance_diameter_mm")

        minimum_width = shared.screw_clearance_diameter_mm + (2 * shared.minimum_wall_mm)
        if shared.arm_width_mm < minimum_width:
            raise ConfigError(f"arm_width_mm must be at least {minimum_width:.2f} mm")
        if self.config.cross.screw_pair_spacing_mm >= shared.arm_width_mm - shared.screw_clearance_diameter_mm:
            raise ConfigError("cross.screw_pair_spacing_mm leaves too little plastic at the arm edges")
        if self.config.column.plate_width_mm < self.config.column.plate_hole_spacing_mm + minimum_width:
            raise ConfigError("column.plate_width_mm is too narrow for its paired plate holes")
        if self.config.column.plate_height_mm < minimum_width:
            raise ConfigError(f"column.plate_height_mm must be at least {minimum_width:.2f} mm")
        hole_radius = shared.screw_clearance_diameter_mm / 2
        hole_y = self.config.column.plate_hole_offset_y_mm
        if abs(hole_y) + hole_radius + shared.minimum_wall_mm > self.config.column.plate_height_mm / 2:
            raise ConfigError("column.plate_hole_offset_y_mm places holes too close to the plate edge")
        if self.config.column.post_width_mm >= self.config.column.plate_width_mm:
            raise ConfigError("column.post_width_mm must be smaller than column.plate_width_mm")
        if self.config.column.post_height_mm >= self.config.column.plate_height_mm:
            raise ConfigError("column.post_height_mm must be smaller than column.plate_height_mm")
        post_min_y = self.config.column.post_offset_y_mm - (self.config.column.post_height_mm / 2)
        post_max_y = self.config.column.post_offset_y_mm + (self.config.column.post_height_mm / 2)
        plate_min_y = -self.config.column.plate_height_mm / 2
        plate_max_y = self.config.column.plate_height_mm / 2
        if post_min_y < plate_min_y or post_max_y > plate_max_y:
            raise ConfigError("column.post_offset_y_mm places the post outside the plate")
        if post_min_y <= hole_y <= post_max_y:
            raise ConfigError("column post overlaps the plate hole row; move one of them in Y")

        if shared.edge_roundover_mm > 0:
            max_roundover = min(shared.bracket_thickness_mm, shared.arm_width_mm) / 2
            if shared.edge_roundover_mm >= max_roundover:
                raise ConfigError(f"edge_roundover_mm must be less than {max_roundover:.2f} mm")


class BracketGeometry:
    def __init__(self, config: BracketConfig) -> None:
        self.config = config

    @property
    def cross_hole_x_mm(self) -> float:
        shared = self.config.shared
        return (shared.panel_gap_x_mm / 2) + shared.hole_offset_x_from_panel_edge_mm

    @property
    def cross_hole_y_mm(self) -> float:
        shared = self.config.shared
        return (shared.panel_gap_y_mm / 2) + shared.hole_offset_y_from_panel_edge_mm

    @property
    def cross_width_mm(self) -> float:
        return (2 * self.cross_hole_x_mm) + (2 * self.config.cross.arm_extension_past_hole_mm)

    @property
    def cross_height_mm(self) -> float:
        return (2 * self.cross_hole_y_mm) + (2 * self.config.cross.arm_extension_past_hole_mm)

    @property
    def cross_holes_mm(self) -> list[tuple[float, float]]:
        pair = self.config.cross.screw_pair_spacing_mm / 2
        return [
            (-self.cross_hole_x_mm, -pair),
            (-self.cross_hole_x_mm, pair),
            (self.cross_hole_x_mm, -pair),
            (self.cross_hole_x_mm, pair),
            (-pair, -self.cross_hole_y_mm),
            (pair, -self.cross_hole_y_mm),
            (-pair, self.cross_hole_y_mm),
            (pair, self.cross_hole_y_mm),
        ]


class BracketGenerator:
    def __init__(self, config: BracketConfig) -> None:
        self.config = config
        self.geometry = BracketGeometry(config)

    def build_cross(self) -> Any:
        cq = self._cadquery()
        shared = self.config.shared
        cross = self.config.cross

        horizontal = cq.Workplane("XY").box(
            self.geometry.cross_width_mm,
            shared.arm_width_mm,
            shared.bracket_thickness_mm,
        )
        vertical = cq.Workplane("XY").box(
            shared.arm_width_mm,
            self.geometry.cross_height_mm,
            shared.bracket_thickness_mm,
        )
        part = horizontal.union(vertical)

        part = self._cut_through_holes(part, self.geometry.cross_holes_mm)
        if shared.counterbore_depth_mm > 0:
            part = self._cut_counterbores(part, self.geometry.cross_holes_mm)
        if cross.center_relief_diameter_mm > 0:
            part = (
                part.faces(">Z")
                .workplane()
                .pushPoints([(0, 0)])
                .hole(cross.center_relief_diameter_mm)
            )
        return self._round_edges(part)

    def build_column(self) -> Any:
        cq = self._cadquery()
        shared = self.config.shared
        column = self.config.column

        plate = cq.Workplane("XY").box(
            column.plate_width_mm,
            column.plate_height_mm,
            shared.bracket_thickness_mm,
            centered=(True, True, False),
        )
        plate_holes = [
            (-column.plate_hole_spacing_mm / 2, column.plate_hole_offset_y_mm),
            (column.plate_hole_spacing_mm / 2, column.plate_hole_offset_y_mm),
        ]
        part = self._cut_through_holes(plate, plate_holes)
        if shared.counterbore_depth_mm > 0:
            part = self._cut_counterbores(part, plate_holes)

        post = (
            cq.Workplane("XY")
            .box(
                column.post_width_mm,
                column.post_height_mm,
                column.post_depth_mm,
                centered=(True, True, False),
            )
            .translate((0, column.post_offset_y_mm, shared.bracket_thickness_mm))
        )
        part = part.union(post)
        return self._round_edges(part)

    def export(self, out_dir: Path, only: str = "all") -> list[Path]:
        cq = self._cadquery()
        out_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        models = []
        if only in {"all", "cross"}:
            models.append(("cross_bracket", self.build_cross()))
        if only in {"all", "column"}:
            models.append(("wall_standoff", self.build_column()))

        for name, model in models:
            stl_path = out_dir / f"{name}.stl"
            step_path = out_dir / f"{name}.step"
            cq.exporters.export(model, str(stl_path))
            cq.exporters.export(model, str(step_path))
            outputs.extend([stl_path, step_path])
        return outputs

    def _cut_through_holes(self, part: Any, holes: list[tuple[float, float]]) -> Any:
        return (
            part.faces(">Z")
            .workplane()
            .pushPoints(holes)
            .hole(self.config.shared.screw_clearance_diameter_mm)
        )

    def _cut_counterbores(self, part: Any, holes: list[tuple[float, float]]) -> Any:
        shared = self.config.shared
        return (
            part.faces(">Z")
            .workplane()
            .pushPoints(holes)
            .cboreHole(
                shared.screw_clearance_diameter_mm,
                shared.screw_head_diameter_mm,
                shared.counterbore_depth_mm,
            )
        )

    def _round_edges(self, part: Any) -> Any:
        roundover = self.config.shared.edge_roundover_mm
        if roundover <= 0:
            return part
        # Fillets on unioned OpenCascade solids can be slow or brittle. Chamfering
        # gives the printed part a less sharp edge while exporting reliably.
        return part.edges("|Z").chamfer(roundover)

    @staticmethod
    def _cadquery() -> Any:
        try:
            import cadquery as cq
        except ImportError as exc:
            raise SystemExit(
                "CadQuery is required to export models. Install it with: "
                "uv pip install cadquery pyyaml"
            ) from exc
        return cq


class BracketCli:
    def run(self) -> None:
        args = self._parse_args()
        config = BracketConfigLoader(args.config).load()
        BracketConfigValidator(config).validate()

        if args.validate_only:
            print(f"Config is valid: {args.config}")
            return

        outputs = BracketGenerator(config).export(args.out, args.only)
        for output in outputs:
            print(output)

    @staticmethod
    def _parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "--config",
            type=Path,
            default=Path(__file__).with_name("bracket_config.example.yaml"),
            help="YAML file containing panel and bracket dimensions.",
        )
        parser.add_argument(
            "--out",
            type=Path,
            default=Path(__file__).with_name("out"),
            help="Directory where STL and STEP files will be written.",
        )
        parser.add_argument(
            "--only",
            choices=["all", "cross", "column"],
            default="all",
            help="Generate only one bracket type, or both.",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Validate the config without importing CadQuery or writing model files.",
        )
        return parser.parse_args()


if __name__ == "__main__":
    BracketCli().run()
