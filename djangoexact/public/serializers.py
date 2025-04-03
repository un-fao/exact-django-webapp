from rest_framework import serializers
import api.serializers as api_serializers
import api.models as models


class PublicProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for public projects.
    """

    class Meta:
        model = models.Project
        fields = ["id", "name"]


class PublicActivitySerializer(serializers.ModelSerializer):
    """
    Serializer for public activities.
    """

    class Meta:
        model = models.Activity
        fields = ["id", "name"]


def get_module_serializer(ModuleClass: models.Module | models.Submodule):
    """
    Function to get the serializer class for a given module or submodule.
    """

    match ModuleClass:
        case models.LandUseChange:
            return PublicLandUseChangeSerializer
        case models.AnnualCropland:
            return PublicAnnualCroplandSerializer
        case models.MinorSeasonAnnualCropland:
            return MinorSeasonAnnualCroplandSerializer
        case models.PerennialCropland:
            return PublicPerennialCroplandSerializer
        case models.MinorSeasonPerennialCropland:
            return MinorSeasonPerennialCroplandSerializer
        case models.FloodedRice:
            return PublicFloodedRiceSerializer
        case models.MinorSeasonFloodedRice:
            return MinorSeasonFloodedRiceSerializer
        case models.SetAside:
            return PublicSetAsideSerializer
        case models.Grassland:
            return PublicGrasslandSerializer
        case models.ForestManagement:
            return PublicForestManagementSerializer
        case models.Settlement:
            return PublicSettlementSerializer
        case models.Road:
            return PublicRoadSerializer
        case models.Building:
            return PublicBuildingSerializer
        case models.OtherInfrastructure:
            return PublicOtherInfrastructureSerializer
        case models.OtherLand:
            return PublicOtherLandSerializer
        case models.OrganicSoil:
            return PublicOrganicSoilSerializer
        case models.CoastalWetland:
            return PublicCoastalWetlandSerializer
        case models.Waterbody:
            return PublicWaterbodySerializer
        case models.Livestock:
            return PublicLivestockSerializer
        case models.SmallFishery:
            return SmallFisherySerializer
        case models.LargeFishery:
            return LargeFisherySerializer
        case models.Aquaculture:
            return PublicAquacultureSerializer
        case models.Irrigation:
            return PublicIrrigationSerializer
        case models.IrrigationPhase:
            return PublicIrrigationPhaseSerializer
        case models.IrrigationSystem:
            return PublicIrrigationSystemSerializer
        case models.Input:
            return PublicInputSerializer
        case models.InputEntry:
            return PublicInputEntrySerializer
        case models.Energy:
            return PublicEnergySerializer
        case models.EnergyEntry:
            return PublicEnergyEntrySerializer
        case models.Packaging:
            return PublicPackagingSerializer
        case models.PackagingEntry:
            return PublicPackagingEntrySerializer
        case models.Transport:
            return PublicTransportSerializer
        case models.TransportEntry:
            return PublicTransportEntrySerializer
        case models.Storage:
            return PublicStorageSerializer
        case models.StorageEntry:
            return PublicStorageEntrySerializer
        case models.Processing:
            return PublicProcessingSerializer
        case models.ProcessingEntry:
            return PublicProcessingEntrySerializer
        case _:
            raise ValueError(f"Unknown module class: {ModuleClass}")


class PublicModuleTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for public module type data.
    """

    class Meta:
        model = models.ModuleType
        fields = ["id", "name"]


class PublicLandUseChangeSerializer(serializers.ModelSerializer):
    """
    Serializer for public land use change data.
    """

    class Meta:
        model = models.LandUseChange
        fields = ["id"]


class PublicAnnualCroplandSerializer(serializers.ModelSerializer):
    """
    Serializer for public annual cropland data.
    """

    class Meta:
        model = models.AnnualCropland
        fields = ["id"]


class MinorSeasonAnnualCroplandSerializer(serializers.ModelSerializer):
    """
    Serializer for public minor season annual cropland data.
    """

    class Meta:
        model = models.MinorSeasonAnnualCropland
        fields = ["id"]


class PublicPerennialCroplandSerializer(serializers.ModelSerializer):
    """
    Serializer for public perennial cropland data.
    """

    module_type = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.PerennialCropland
        fields = ["id", "module_type"]


class MinorSeasonPerennialCroplandSerializer(serializers.ModelSerializer):
    """
    Serializer for public minor season perennial cropland data.
    """

    class Meta:
        model = models.MinorSeasonPerennialCropland
        fields = ["id"]


class PublicFloodedRiceSerializer(serializers.ModelSerializer):
    """
    Serializer for public flooded rice data.
    """

    class Meta:
        model = models.FloodedRice
        fields = ["id"]


class MinorSeasonFloodedRiceSerializer(serializers.ModelSerializer):
    """
    Serializer for public minor season flooded rice data.
    """

    class Meta:
        model = models.MinorSeasonFloodedRice
        fields = ["id"]


class PublicSetAsideSerializer(serializers.ModelSerializer):
    """
    Serializer for public set aside data.
    """

    class Meta:
        model = models.SetAside
        fields = ["id"]


class PublicGrasslandSerializer(serializers.ModelSerializer):
    """
    Serializer for public grassland data.
    """

    class Meta:
        model = models.Grassland
        fields = ["id"]


class PublicForestManagementSerializer(serializers.ModelSerializer):
    """
    Serializer for public forest management data.
    """

    class Meta:
        model = models.ForestManagement
        fields = ["id"]


class PublicSettlementSerializer(serializers.ModelSerializer):
    """
    Serializer for public settlement data.
    """

    class Meta:
        model = models.Settlement
        fields = ["id"]


class PublicRoadSerializer(serializers.ModelSerializer):
    """
    Serializer for public road data.
    """

    class Meta:
        model = models.Road
        fields = ["id"]


class PublicBuildingSerializer(serializers.ModelSerializer):
    """
    Serializer for public building data.
    """

    class Meta:
        model = models.Building
        fields = ["id"]


class PublicOtherInfrastructureSerializer(serializers.ModelSerializer):
    """
    Serializer for public other infrastructure data.
    """

    class Meta:
        model = models.OtherInfrastructure
        fields = ["id"]


class PublicOtherLandSerializer(serializers.ModelSerializer):
    """
    Serializer for public other land data.
    """

    class Meta:
        model = models.OtherLand
        fields = ["id"]


class PublicOrganicSoilSerializer(serializers.ModelSerializer):
    """
    Serializer for public organic soil data.
    """

    class Meta:
        model = models.OrganicSoil
        fields = ["id"]


class PublicCoastalWetlandSerializer(serializers.ModelSerializer):
    """
    Serializer for public coastal wetland data.
    """

    class Meta:
        model = models.CoastalWetland
        fields = ["id"]


class PublicWaterbodySerializer(serializers.ModelSerializer):
    """
    Serializer for public water body data.
    """

    class Meta:
        model = models.Waterbody
        fields = ["id"]


class PublicLivestockSerializer(serializers.ModelSerializer):
    """
    Serializer for public livestock data.
    """

    class Meta:
        model = models.Livestock
        fields = ["id"]


class SmallFisherySerializer(serializers.ModelSerializer):
    """
    Serializer for public small fishery data.
    """

    class Meta:
        model = models.SmallFishery
        fields = ["id"]


class LargeFisherySerializer(serializers.ModelSerializer):
    """
    Serializer for public large fishery data.
    """

    class Meta:
        model = models.LargeFishery
        fields = ["id"]


class PublicAquacultureSerializer(serializers.ModelSerializer):
    """
    Serializer for public aquaculture data.
    """

    class Meta:
        model = models.Aquaculture
        fields = ["id"]


class PublicIrrigationSerializer(serializers.ModelSerializer):
    """
    Serializer for public irrigation data.
    """

    class Meta:
        model = models.Irrigation
        fields = ["id"]


class PublicIrrigationPhaseSerializer(serializers.ModelSerializer):
    """
    Serializer for public irrigation phase data.
    """

    class Meta:
        model = models.IrrigationPhase
        fields = ["id"]


class PublicIrrigationSystemSerializer(serializers.ModelSerializer):
    """
    Serializer for public irrigation system data.
    """

    class Meta:
        model = models.IrrigationSystem
        fields = ["id"]


class PublicInputSerializer(serializers.ModelSerializer):
    """
    Serializer for public input data.
    """

    class Meta:
        model = models.Input
        fields = ["id"]


class PublicInputEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for public input entry data.
    """

    class Meta:
        model = models.InputEntry
        fields = ["id"]


class PublicEnergySerializer(serializers.ModelSerializer):
    """
    Serializer for public energy data.
    """

    class Meta:
        model = models.Energy
        fields = ["id"]


class PublicEnergyEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for public energy entry data.
    """

    class Meta:
        model = models.EnergyEntry
        fields = ["id"]


class PublicPackagingSerializer(serializers.ModelSerializer):
    """
    Serializer for public packaging data.
    """

    class Meta:
        model = models.Packaging
        fields = ["id"]


class PublicPackagingEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for public packaging entry data.
    """

    class Meta:
        model = models.PackagingEntry
        fields = ["id"]


class PublicTransportSerializer(serializers.ModelSerializer):
    """
    Serializer for public transport data.
    """

    class Meta:
        model = models.Transport
        fields = ["id"]


class PublicTransportEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for public transport entry data.
    """

    class Meta:
        model = models.TransportEntry
        fields = ["id"]


class PublicStorageSerializer(serializers.ModelSerializer):
    """
    Serializer for public storage data.
    """

    class Meta:
        model = models.Storage
        fields = ["id"]


class PublicStorageEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for public storage entry data.
    """

    class Meta:
        model = models.StorageEntry
        fields = ["id"]


class PublicProcessingSerializer(serializers.ModelSerializer):
    """
    Serializer for public processing data.
    """

    class Meta:
        model = models.Processing
        fields = ["id"]


class PublicProcessingEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for public processing entry data.
    """

    class Meta:
        model = models.ProcessingEntry
        fields = ["id"]
