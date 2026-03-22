"""IfcOpenShell を用いた IFC4 壁モデル生成モジュール."""

from __future__ import annotations

import math
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import ifcopenshell
import ifcopenshell.guid

if TYPE_CHECKING:
    pass


def _guid() -> str:
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def generate_ifc(walls: list, scale_factor: float, output_path: Path) -> None:
    """壁データのリストから IFC4 ファイルを生成して *output_path* に書き出す."""

    ifc = ifcopenshell.file(schema="IFC4")

    # ---------- ヘッダ ----------
    ifc.header.file_description.description = ("ViewDefinition[CoordinationView]",)
    ifc.header.file_name.name = str(output_path)
    ifc.header.file_name.time_stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    ifc.header.file_name.author = ("PDF-to-IFC PoC",)
    ifc.header.file_name.organization = ("PoC",)

    # ---------- 共通エンティティ ----------
    owner_history = _create_owner_history(ifc)
    context = ifc.createIfcGeometricRepresentationContext(
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=ifc.createIfcAxis2Placement3D(
            Location=ifc.createIfcCartesianPoint((0.0, 0.0, 0.0)),
        ),
    )
    body_context = ifc.createIfcGeometricRepresentationSubContext(
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=context,
        TargetView="MODEL_VIEW",
    )

    site_placement = ifc.createIfcLocalPlacement(
        RelativePlacement=ifc.createIfcAxis2Placement3D(
            Location=ifc.createIfcCartesianPoint((0.0, 0.0, 0.0)),
        )
    )
    site = ifc.createIfcSite(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name="Site",
        CompositionType="ELEMENT",
        ObjectPlacement=site_placement,
    )

    building_placement = ifc.createIfcLocalPlacement(
        PlacementRelTo=site_placement,
        RelativePlacement=ifc.createIfcAxis2Placement3D(
            Location=ifc.createIfcCartesianPoint((0.0, 0.0, 0.0)),
        ),
    )
    building = ifc.createIfcBuilding(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name="Building",
        CompositionType="ELEMENT",
        ObjectPlacement=building_placement,
    )

    storey_placement = ifc.createIfcLocalPlacement(
        PlacementRelTo=building_placement,
        RelativePlacement=ifc.createIfcAxis2Placement3D(
            Location=ifc.createIfcCartesianPoint((0.0, 0.0, 0.0)),
        ),
    )
    storey = ifc.createIfcBuildingStorey(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name="Ground Floor",
        CompositionType="ELEMENT",
        ObjectPlacement=storey_placement,
        Elevation=0.0,
    )

    project = ifc.createIfcProject(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name="PDF-to-IFC PoC",
        RepresentationContexts=[context],
        UnitsInContext=_create_units(ifc),
    )

    ifc.createIfcRelAggregates(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        RelatingObject=project,
        RelatedObjects=[site],
    )
    ifc.createIfcRelAggregates(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        RelatingObject=site,
        RelatedObjects=[building],
    )
    ifc.createIfcRelAggregates(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        RelatingObject=building,
        RelatedObjects=[storey],
    )

    # ---------- 壁の生成 ----------
    wall_elements: list = []
    for idx, w in enumerate(walls):
        sx = w.start_point.x * scale_factor
        sy = w.start_point.y * scale_factor
        ex = w.end_point.x * scale_factor
        ey = w.end_point.y * scale_factor
        height = w.height
        thickness = w.thickness

        wall_elem = _create_wall(
            ifc,
            owner_history,
            body_context,
            storey_placement,
            idx,
            sx, sy, ex, ey,
            height,
            thickness,
        )
        wall_elements.append(wall_elem)

    if wall_elements:
        ifc.createIfcRelContainedInSpatialStructure(
            GlobalId=_guid(),
            OwnerHistory=owner_history,
            RelatingStructure=storey,
            RelatedElements=wall_elements,
        )

    ifc.write(str(output_path))


def _create_wall(
    ifc,
    owner_history,
    body_context,
    storey_placement,
    idx: int,
    sx: float, sy: float,
    ex: float, ey: float,
    height: float,
    thickness: float,
):
    """始点・終点・高さ・厚みから IfcWall + SweptSolid を生成."""

    dx = ex - sx
    dy = ey - sy
    length = math.hypot(dx, dy)
    if length < 1e-6:
        raise ValueError(f"Wall {idx}: 始点と終点が同一です。")

    dir_x = dx / length
    dir_y = dy / length

    wall_placement = ifc.createIfcLocalPlacement(
        PlacementRelTo=storey_placement,
        RelativePlacement=ifc.createIfcAxis2Placement3D(
            Location=ifc.createIfcCartesianPoint((sx, sy, 0.0)),
            Axis=ifc.createIfcDirection((0.0, 0.0, 1.0)),
            RefDirection=ifc.createIfcDirection((dir_x, dir_y, 0.0)),
        ),
    )

    profile = ifc.createIfcRectangleProfileDef(
        ProfileType="AREA",
        XDim=length,
        YDim=thickness,
        Position=ifc.createIfcAxis2Placement2D(
            Location=ifc.createIfcCartesianPoint((length / 2.0, 0.0)),
        ),
    )

    solid = ifc.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=ifc.createIfcAxis2Placement3D(
            Location=ifc.createIfcCartesianPoint((0.0, 0.0, 0.0)),
        ),
        ExtrudedDirection=ifc.createIfcDirection((0.0, 0.0, 1.0)),
        Depth=height,
    )

    shape = ifc.createIfcShapeRepresentation(
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    product_shape = ifc.createIfcProductDefinitionShape(Representations=[shape])

    wall = ifc.createIfcWall(
        GlobalId=_guid(),
        OwnerHistory=owner_history,
        Name=f"Wall_{idx + 1}",
        ObjectPlacement=wall_placement,
        Representation=product_shape,
    )
    return wall


def _create_owner_history(ifc):
    person = ifc.createIfcPerson(FamilyName="User")
    org = ifc.createIfcOrganization(Name="PoC")
    person_org = ifc.createIfcPersonAndOrganization(ThePerson=person, TheOrganization=org)
    app = ifc.createIfcApplication(
        ApplicationDeveloper=org,
        Version="0.1",
        ApplicationFullName="PDF-to-IFC PoC",
        ApplicationIdentifier="pdf-to-ifc",
    )
    return ifc.createIfcOwnerHistory(
        OwningUser=person_org,
        OwningApplication=app,
        ChangeAction="NOCHANGE",
        CreationDate=int(time.time()),
    )


def _create_units(ifc):
    length = ifc.createIfcSIUnit(UnitType="LENGTHUNIT", Name="METRE", Prefix="MILLI")
    area = ifc.createIfcSIUnit(UnitType="AREAUNIT", Name="SQUARE_METRE")
    volume = ifc.createIfcSIUnit(UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
    angle = ifc.createIfcSIUnit(UnitType="PLANEANGLEUNIT", Name="RADIAN")
    return ifc.createIfcUnitAssignment(Units=[length, area, volume, angle])
