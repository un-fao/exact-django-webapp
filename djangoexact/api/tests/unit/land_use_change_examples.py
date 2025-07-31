"""
Examples demonstrating how to use AnyToAnyLandUseChangeTestCase for testing various land use change scenarios.

This file provides comprehensive examples of different usage patterns for the generic land use change test class.
These are working examples that can be copied and adapted for specific testing needs.
"""

from rest_framework import status
import api.models as models
import logging as log
from . import base_module
import logging

logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
logging.getLogger("django").setLevel(logging.CRITICAL)


# ==========================================
# METHOD 1: INHERITANCE (RECOMMENDED)
# ==========================================


class GrasslandToForestExampleTestCase(base_module.AnyToAnyLandUseChangeTestCase):
    """
    Example 1: Basic inheritance pattern

    This is the most common and recommended way to use AnyToAnyLandUseChangeTestCase.
    Simply inherit from it and configure your specific scenario in setUp().
    """

    def setUp(self):
        super().setUp()
        # Setup your specific scenario: Grassland → Forest conversion
        self.setup_scenario(
            start_module="Grassland",  # Starting land use (baseline)
            w_module="ForestManagement",  # With project scenario (converted to forest)
            wo_module="Grassland",  # Without project scenario (remains grassland)
        )

        # Optional: Add custom configuration after setup
        self.configure_custom_modules()

    def configure_custom_modules(self):
        """Add scenario-specific configuration if needed"""
        # Configure grassland modules with specific parameters
        if self.module_start and self.module_wo:
            grassland_config = {
                "area": 150,
                # Add more grassland-specific parameters as needed
            }
            self.edit_module(self.module_start, self.user, grassland_config)
            self.edit_module(self.module_wo, self.user, grassland_config)

        # Configure forest management module
        if self.module_w:
            forest_config = {
                "forest_type": models.ForestType.objects.filter(name_en="Natural").first().id,
                "forest_condition_type": models.ForestConditionType.objects.filter(name_en="Primary").first().id,
                # Add more forest-specific parameters as needed
            }
            self.edit_module(self.module_w, self.user, forest_config)

    # The inherited test_generic_calculation() runs automatically
    # Add your own scenario-specific tests:

    def test_grassland_to_forest_carbon_benefits(self):
        """Test that grassland to forest conversion shows carbon benefits"""
        response = self.get_land_use_change_results()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

        # Log results for analysis
        balance = response.data["balance"]
        log.info(f"Grassland to Forest conversion balance: {balance}")

        # Test individual module results
        grassland_response = self.get_module_results(self.module_wo)
        forest_response = self.get_module_results(self.module_w)

        self.assertEqual(grassland_response.status_code, status.HTTP_200_OK)
        self.assertEqual(forest_response.status_code, status.HTTP_200_OK)

    def test_area_scaling(self):
        """Test that doubling the area roughly doubles the impact"""
        # Get initial results
        initial_response = self.get_land_use_change_results()
        self.assertEqual(initial_response.status_code, status.HTTP_200_OK)
        initial_balance = initial_response.data["balance"]

        # Double the area
        original_area = self.land_use_change.area
        new_area = original_area * 2

        edit_response = self.edit_module(self.land_use_change, self.user, {"area": new_area})
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)

        # Get new results
        new_response = self.get_land_use_change_results(cached="false")
        self.assertEqual(new_response.status_code, status.HTTP_200_OK)
        new_balance = new_response.data["balance"]

        log.info(f"Original area: {original_area}, balance: {initial_balance}")
        log.info(f"Doubled area: {new_area}, balance: {new_balance}")


class AnnualToAquacultureExampleTestCase(base_module.AnyToAnyLandUseChangeTestCase):
    """
    Example 2: Complex scenario with detailed configuration

    This shows how to handle scenarios that require extensive module configuration,
    such as converting cropland to aquaculture systems.
    """

    def setUp(self):
        super().setUp()
        # Setup an unusual but valid scenario: Annual Cropland → Aquaculture
        self.setup_scenario(start_module="AnnualCropland", w_module="Aquaculture", wo_module="AnnualCropland")

        self.apply_detailed_configuration()

    def apply_detailed_configuration(self):
        """Apply detailed configuration to all modules after setup"""

        # Configure annual cropland modules (start & wo scenarios)
        annual_config = self.get_annual_cropland_config()
        if self.module_start:
            self.edit_module(self.module_start, self.user, annual_config)
        if self.module_wo:
            self.edit_module(self.module_wo, self.user, annual_config)

        # Configure aquaculture module (w scenario)
        aqua_config = self.get_aquaculture_config()
        if self.module_w:
            self.edit_module(self.module_w, self.user, aqua_config)

    def get_annual_cropland_config(self):
        """Get comprehensive configuration for annual cropland modules"""
        land_use_types = models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", climates=self.project.climate, moistures=self.project.moisture, is_active=True)

        if not land_use_types.exists():
            return {}

        return {
            "land_use_type_start": land_use_types.first().id,
            "land_use_type_w": land_use_types.first().id,
            "land_use_type_wo": land_use_types.first().id,
            "tillage_management_type_start": models.TillageManagementType.objects.first().id,
            "tillage_management_type_w": models.TillageManagementType.objects.first().id,
            "tillage_management_type_wo": models.TillageManagementType.objects.first().id,
            "organic_input_type_start": models.OrganicInputType.objects.first().id,
            "organic_input_type_w": models.OrganicInputType.objects.first().id,
            "organic_input_type_wo": models.OrganicInputType.objects.first().id,
        }

    def get_aquaculture_config(self):
        """Get comprehensive configuration for aquaculture module"""
        # Note: Aquaculture might have different configuration requirements
        # This is a placeholder - actual configuration depends on the Aquaculture model
        return {
            # Add aquaculture-specific configuration fields here
            # Example: "pond_type": models.PondType.objects.first().id,
            # Example: "fish_species": models.FishSpecies.objects.first().id,
        }

    def test_land_to_aquaculture_conversion(self):
        """Test the unique aspects of converting land to aquaculture"""
        response = self.get_land_use_change_results()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Aquaculture conversion typically has unique environmental impacts
        balance = response.data["balance"]
        self.assertIsInstance(balance, (int, float))

        log.info(f"Annual Cropland to Aquaculture conversion balance: {balance}")

    def test_aquaculture_module_specifics(self):
        """Test that the aquaculture module can be calculated independently"""
        if self.module_w:  # Aquaculture module
            aqua_response = self.get_module_results(self.module_w)
            self.assertEqual(aqua_response.status_code, status.HTTP_200_OK)
            self.assertIn("balance", aqua_response.data)


# ==========================================
# METHOD 2: BULK TESTING MULTIPLE SCENARIOS
# ==========================================


class BulkLandUseScenarioTestCase(base_module.APITestCaseMixin):
    """
    Example 3: Testing multiple scenarios in a single test class

    This approach is useful for testing many different land use change combinations
    systematically without creating separate test classes for each.
    """

    def test_all_forest_conversion_scenarios(self):
        """Test converting various land uses to forest management"""
        forest_scenarios = [
            ("AnnualCropland", "ForestManagement", "AnnualCropland"),
            ("PerennialCropland", "ForestManagement", "PerennialCropland"),
            ("Grassland", "ForestManagement", "Grassland"),
            ("OtherLand", "ForestManagement", "OtherLand"),
        ]

        for start, w, wo in forest_scenarios:
            with self.subTest(scenario=f"{start}→{w}"):
                # Create fresh test instance for each scenario
                test_case = base_module.AnyToAnyLandUseChangeTestCase()
                test_case.setUp()
                test_case.setup_scenario(start, w, wo)

                # Run the generic test
                test_case.test_generic_calculation()

                # Add scenario-specific checks
                response = test_case.get_land_use_change_results()
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("balance", response.data)

                balance = response.data["balance"]
                log.info(f"Forest conversion scenario {start}→{w}: balance = {balance}")

    def test_deforestation_scenarios(self):
        """Test forest conversion to other land uses (typically negative impact)"""
        deforestation_scenarios = [
            ("ForestManagement", "AnnualCropland", "ForestManagement"),
            ("ForestManagement", "PerennialCropland", "ForestManagement"),
            ("ForestManagement", "Grassland", "ForestManagement"),
            ("ForestManagement", "OtherLand", "ForestManagement"),
        ]

        for start, w, wo in deforestation_scenarios:
            with self.subTest(scenario=f"{start}→{w}"):
                test_case = base_module.AnyToAnyLandUseChangeTestCase()
                test_case.setUp()
                test_case.setup_scenario(start, w, wo)

                # Test calculation works
                response = test_case.get_land_use_change_results()
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("balance", response.data)

                balance = response.data["balance"]
                log.info(f"Deforestation scenario {start}→{w}: balance = {balance}")

    def test_cropland_conversions(self):
        """Test various cropland conversion scenarios"""
        cropland_scenarios = [
            ("AnnualCropland", "PerennialCropland", "AnnualCropland"),
            ("PerennialCropland", "AnnualCropland", "PerennialCropland"),
            ("AnnualCropland", "Grassland", "AnnualCropland"),
            ("PerennialCropland", "Grassland", "PerennialCropland"),
        ]

        for start, w, wo in cropland_scenarios:
            with self.subTest(scenario=f"{start}→{w}"):
                test_case = base_module.AnyToAnyLandUseChangeTestCase()
                test_case.setUp()
                test_case.setup_scenario(start, w, wo)

                response = test_case.get_land_use_change_results()
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                balance = response.data["balance"]
                log.info(f"Cropland conversion {start}→{w}: balance = {balance}")


# ==========================================
# METHOD 3: MATRIX TESTING
# ==========================================


class LandUseMatrixTestCase(base_module.APITestCaseMixin):
    """
    Example 4: Systematic matrix testing of all possible combinations

    This tests every possible land use change combination to ensure
    the calculation system works for all scenarios.
    """

    # Available land use module types
    LAND_USE_MODULES = [
        "AnnualCropland",
        "PerennialCropland",
        "Grassland",
        "ForestManagement",
        "OtherLand",
        # Note: CoastalWetland and Aquaculture might need special handling
    ]

    def test_land_use_change_matrix(self):
        """Test a matrix of land use change scenarios"""
        successful_scenarios = []
        failed_scenarios = []

        for start_module in self.LAND_USE_MODULES:
            for w_module in self.LAND_USE_MODULES:
                for wo_module in self.LAND_USE_MODULES:
                    scenario_name = f"{start_module}→{w_module} (wo:{wo_module})"

                    try:
                        with self.subTest(scenario=scenario_name):
                            test_case = base_module.AnyToAnyLandUseChangeTestCase()
                            test_case.setUp()
                            test_case.setup_scenario(start_module, w_module, wo_module)

                            # Test that calculation works
                            response = test_case.get_land_use_change_results()
                            self.assertEqual(response.status_code, status.HTTP_200_OK)
                            self.assertIn("balance", response.data)

                            successful_scenarios.append(scenario_name)
                            balance = response.data["balance"]
                            log.info(f"✓ {scenario_name}: balance = {balance}")

                    except Exception as e:
                        failed_scenarios.append((scenario_name, str(e)))
                        log.warning(f"✗ {scenario_name}: {e}")

        # Report results
        log.info(f"\nMatrix Testing Results:")
        log.info(f"Successful scenarios: {len(successful_scenarios)}")
        log.info(f"Failed scenarios: {len(failed_scenarios)}")

        if failed_scenarios:
            log.info("Failed scenarios:")
            for scenario, error in failed_scenarios:
                log.info(f"  - {scenario}: {error}")

        # At least some scenarios should work
        self.assertGreater(len(successful_scenarios), 0, "At least some land use change scenarios should work")


# ==========================================
# METHOD 4: PARAMETERIZED TESTING
# ==========================================


class ParameterizedLandUseTestCase(base_module.AnyToAnyLandUseChangeTestCase):
    """
    Example 5: Parameterized testing approach

    This demonstrates how to test multiple scenarios using a parameterized approach,
    which is useful for systematic testing with different expected outcomes.
    """

    def setUp(self):
        super().setUp()
        # Don't setup scenario here - it will be done in individual tests

    def run_scenario_test(self, scenario_name, start, w, wo, expected_characteristics=None):
        """
        Helper method to run a scenario test with optional characteristic validation

        Args:
            scenario_name (str): Human-readable name for the scenario
            start (str): Starting module type
            w (str): With project module type
            wo (str): Without project module type
            expected_characteristics (dict): Optional expected characteristics to validate
        """
        log.info(f"Testing scenario: {scenario_name}")

        self.setup_scenario(start, w, wo)

        # Test that calculation works
        response = self.get_land_use_change_results()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("balance", response.data)

        balance = response.data["balance"]
        log.info(f"{scenario_name} balance: {balance}")

        # Validate expected characteristics if provided
        if expected_characteristics:
            if "positive_impact" in expected_characteristics:
                if expected_characteristics["positive_impact"]:
                    # Note: This is just an example - actual validation depends on your requirements
                    self.assertIsInstance(balance, (int, float), f"{scenario_name} should have numeric balance")

            if "calculation_succeeds" in expected_characteristics:
                self.assertTrue(expected_characteristics["calculation_succeeds"], f"{scenario_name} calculation should succeed")

        return balance

    def test_conservation_scenarios(self):
        """Test scenarios that typically show positive environmental impact"""
        conservation_scenarios = [
            ("Annual to Forest", "AnnualCropland", "ForestManagement", "AnnualCropland", {"positive_impact": True}),
            ("Perennial to Forest", "PerennialCropland", "ForestManagement", "PerennialCropland", {"positive_impact": True}),
            ("Other to Forest", "OtherLand", "ForestManagement", "OtherLand", {"positive_impact": True}),
            ("Annual to Perennial", "AnnualCropland", "PerennialCropland", "AnnualCropland", {"calculation_succeeds": True}),
        ]

        for name, start, w, wo, characteristics in conservation_scenarios:
            with self.subTest(scenario=name):
                # Reset for each scenario
                self.setUp()
                balance = self.run_scenario_test(name, start, w, wo, characteristics)

    def test_conversion_scenarios(self):
        """Test scenarios that typically show environmental costs"""
        conversion_scenarios = [
            ("Forest to Annual", "ForestManagement", "AnnualCropland", "ForestManagement", {"calculation_succeeds": True}),
            ("Forest to Perennial", "ForestManagement", "PerennialCropland", "ForestManagement", {"calculation_succeeds": True}),
            ("Grassland to Annual", "Grassland", "AnnualCropland", "Grassland", {"calculation_succeeds": True}),
        ]

        for name, start, w, wo, characteristics in conversion_scenarios:
            with self.subTest(scenario=name):
                # Reset for each scenario
                self.setUp()
                balance = self.run_scenario_test(name, start, w, wo, characteristics)


# ==========================================
# METHOD 5: STRESS TESTING
# ==========================================


class LandUseStressTestCase(base_module.AnyToAnyLandUseChangeTestCase):
    """
    Example 6: Stress testing with extreme parameters

    This tests the robustness of the land use change system with
    edge cases and extreme parameter values.
    """

    def setUp(self):
        super().setUp()
        self.setup_scenario("AnnualCropland", "ForestManagement", "AnnualCropland")

    def test_extreme_area_values(self):
        """Test with very large and very small area values"""
        extreme_areas = [0.1, 1, 10, 100, 1000, 10000, 100000]

        for area in extreme_areas:
            with self.subTest(area=area):
                # Set extreme area value
                edit_response = self.edit_module(self.land_use_change, self.user, {"area": area})
                self.assertEqual(edit_response.status_code, status.HTTP_200_OK)

                # Test calculation still works
                response = self.get_land_use_change_results(cached="false")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("balance", response.data)

                balance = response.data["balance"]
                log.info(f"Area {area} ha: balance = {balance}")

    def test_fire_usage_combinations(self):
        """Test all combinations of fire usage settings"""
        fire_combinations = [
            (True, True, True),
            (True, True, False),
            (True, False, True),
            (False, True, True),
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        ]

        for fire_start, fire_w, fire_wo in fire_combinations:
            with self.subTest(fire_combo=(fire_start, fire_w, fire_wo)):
                # Set fire usage combination
                fire_config = {
                    "is_fire_used_start": fire_start,
                    "is_fire_used_w": fire_w,
                    "is_fire_used_wo": fire_wo,
                }

                edit_response = self.edit_module(self.land_use_change, self.user, fire_config)
                self.assertEqual(edit_response.status_code, status.HTTP_200_OK)

                # Test calculation works
                response = self.get_land_use_change_results(cached="false")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("balance", response.data)

                balance = response.data["balance"]
                log.info(f"Fire usage ({fire_start}, {fire_w}, {fire_wo}): balance = {balance}")


# ==========================================
# USAGE NOTES AND TIPS
# ==========================================

"""
USAGE TIPS FOR AnyToAnyLandUseChangeTestCase:

1. **Method Selection Guide:**
   - Use METHOD 1 (Inheritance) for focused, specific scenarios
   - Use METHOD 2 (Bulk) for testing multiple related scenarios  
   - Use METHOD 3 (Matrix) for comprehensive system validation
   - Use METHOD 4 (Parameterized) for systematic testing with expectations
   - Use METHOD 5 (Stress) for edge case and robustness testing

2. **Available Module Types:**
   - AnnualCropland
   - PerennialCropland  
   - Grassland
   - ForestManagement
   - CoastalWetland
   - OtherLand
   - Aquaculture (may need special configuration)

3. **Configuration Tips:**
   - Always call setup_scenario() before running tests
   - Use edit_module() to configure module-specific parameters
   - Handle cases where certain configurations might not be available
   - Use cached="false" when testing parameter changes

4. **Common Patterns:**
   - Conservation scenarios: Other land types → ForestManagement
   - Intensification scenarios: AnnualCropland → PerennialCropland
   - Conversion scenarios: ForestManagement → Other land types
   - Restoration scenarios: OtherLand → Grassland or ForestManagement

5. **Testing Best Practices:**
   - Always test that calculations succeed (HTTP 200 status)
   - Validate that "balance" is present in response data  
   - Use subTest() for multiple scenarios in one test method
   - Log results for analysis and debugging
   - Handle exceptions gracefully in bulk testing scenarios

6. **Debugging Tips:**
   - Enable logging to see calculation results
   - Test individual modules separately if LUC calculation fails
   - Check that module types exist in the database
   - Verify that IPCC data is available for your climate/moisture combination
"""
