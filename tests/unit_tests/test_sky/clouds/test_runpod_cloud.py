"""Test the RunPod cloud class."""

import unittest.mock as mock

import pytest

from sky import clouds
from sky.clouds import runpod as runpod_mod


class TestRunPodRegionsWithOffering:
    """Test RunPod.regions_with_offering() with different parameter combinations."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock zones and regions for tests."""
        # Create mock zones
        self.zone_us_il_1 = mock.Mock()
        self.zone_us_il_1.name = 'US-IL-1'

        self.zone_us_ca_1 = mock.Mock()
        self.zone_us_ca_1.name = 'US-CA-1'

        # Create mock region with zones
        self.region_us = clouds.Region('US')
        self.region_us.zones = [self.zone_us_il_1, self.zone_us_ca_1]

    @mock.patch('sky.catalog.get_region_zones_for_accelerators')
    def test_accelerator_only_queries_accelerator_catalog(
            self, mock_get_acc_regions):
        """Test with only accelerator specified (no instance_type).

        This is the primary fix - previously this would fail because
        accelerators were ignored completely.
        """
        mock_get_acc_regions.return_value = [self.region_us]

        result = runpod_mod.RunPod.regions_with_offering(
            instance_type=None,
            accelerators={'RTX5090': 1},
            use_spot=False,
            region='US',
            zone='US-IL-1')

        # Verify catalog was queried with accelerator
        mock_get_acc_regions.assert_called_once_with('RTX5090',
                                                      1,
                                                      False,
                                                      clouds='runpod')

        # Verify result contains filtered zone
        assert len(result) == 1
        assert result[0].name == 'US'
        assert len(result[0].zones) == 1
        assert result[0].zones[0].name == 'US-IL-1'

    @mock.patch('sky.catalog.get_region_zones_for_instance_type')
    def test_instance_type_only_backward_compatible(
            self, mock_get_vm_regions):
        """Test with only instance_type (no accelerator).

        This should still work as before - regression test.
        """
        mock_get_vm_regions.return_value = [self.region_us]

        result = runpod_mod.RunPod.regions_with_offering(
            instance_type='1x_RTX5090_SECURE',
            accelerators=None,
            use_spot=False,
            region='US',
            zone='US-IL-1')

        # Verify catalog was queried with instance_type
        mock_get_vm_regions.assert_called_once_with('1x_RTX5090_SECURE',
                                                     False, 'runpod')

        # Verify result
        assert len(result) == 1
        assert result[0].name == 'US'

    @mock.patch('sky.catalog.get_region_zones_for_accelerators')
    @mock.patch('sky.catalog.get_region_zones_for_instance_type')
    def test_both_specified_returns_intersection(self, mock_get_vm_regions,
                                                  mock_get_acc_regions):
        """Test with both instance_type and accelerator.

        Should return intersection of regions/zones that support both.
        """
        # Accelerator regions: US with IL-1 and CA-1
        acc_region = clouds.Region('US')
        acc_zone1 = mock.Mock()
        acc_zone1.name = 'US-IL-1'
        acc_zone2 = mock.Mock()
        acc_zone2.name = 'US-CA-1'
        acc_region.zones = [acc_zone1, acc_zone2]

        # Instance type regions: US with only IL-1
        vm_region = clouds.Region('US')
        vm_zone1 = mock.Mock()
        vm_zone1.name = 'US-IL-1'
        vm_region.zones = [vm_zone1]

        mock_get_acc_regions.return_value = [acc_region]
        mock_get_vm_regions.return_value = [vm_region]

        result = runpod_mod.RunPod.regions_with_offering(
            instance_type='1x_RTX5090_SECURE',
            accelerators={'RTX5090': 1},
            use_spot=False,
            region='US',
            zone=None)

        # Verify both catalogs were queried
        mock_get_acc_regions.assert_called_once_with('RTX5090',
                                                      1,
                                                      False,
                                                      clouds='runpod')
        mock_get_vm_regions.assert_called_once_with('1x_RTX5090_SECURE',
                                                     False, 'runpod')

        # Verify result - should only have US-IL-1 (intersection)
        assert len(result) == 1
        assert result[0].name == 'US'
        assert len(result[0].zones) == 1
        assert result[0].zones[0].name == 'US-IL-1'

    @mock.patch('sky.catalog.get_region_zones_for_accelerators')
    def test_region_filter_excludes_non_matching(self, mock_get_acc_regions):
        """Test that region filter properly excludes non-matching regions."""
        # Return EU region
        region_eu = clouds.Region('EU')
        zone_eu = mock.Mock()
        zone_eu.name = 'EU-WEST-1'
        region_eu.zones = [zone_eu]
        mock_get_acc_regions.return_value = [region_eu]

        # Filter for US region (won't match EU)
        result = runpod_mod.RunPod.regions_with_offering(
            instance_type=None,
            accelerators={'RTX5090': 1},
            use_spot=False,
            region='US',
            zone=None)

        # Verify result is empty (no matching region)
        assert len(result) == 0

    @mock.patch('sky.catalog.get_region_zones_for_accelerators')
    def test_zone_filter_applied_correctly(self, mock_get_acc_regions):
        """Test that zone filtering works correctly."""
        mock_get_acc_regions.return_value = [self.region_us]

        result = runpod_mod.RunPod.regions_with_offering(
            instance_type=None,
            accelerators={'RTX5090': 1},
            use_spot=False,
            region='US',
            zone='US-IL-1')

        # Verify only IL-1 zone in result
        assert len(result) == 1
        assert len(result[0].zones) == 1
        assert result[0].zones[0].name == 'US-IL-1'

    @mock.patch('sky.catalog.get_region_zones_for_accelerators')
    @mock.patch('sky.catalog.get_region_zones_for_instance_type')
    def test_no_intersection_returns_empty(self, mock_get_vm_regions,
                                           mock_get_acc_regions):
        """Test when accelerator and instance_type have no overlapping regions."""
        # Accelerator only in EU
        acc_region = clouds.Region('EU')
        acc_zone = mock.Mock()
        acc_zone.name = 'EU-WEST-1'
        acc_region.zones = [acc_zone]

        # Instance type only in US
        vm_region = clouds.Region('US')
        vm_zone = mock.Mock()
        vm_zone.name = 'US-EAST-1'
        vm_region.zones = [vm_zone]

        mock_get_acc_regions.return_value = [acc_region]
        mock_get_vm_regions.return_value = [vm_region]

        result = runpod_mod.RunPod.regions_with_offering(
            instance_type='some_instance',
            accelerators={'RTX5090': 1},
            use_spot=False,
            region=None,
            zone=None)

        # No intersection - should be empty
        assert len(result) == 0


class TestRunPodCredentials:
    """Test RunPod credential validation."""

    @mock.patch('os.path.exists')
    def test_missing_config_file(self, mock_exists):
        """Test when ~/.runpod/config.toml doesn't exist."""
        mock_exists.return_value = False

        valid, reason = runpod_mod.RunPod._check_runpod_credentials()

        assert valid is False
        assert 'does not exist' in reason

    @mock.patch('builtins.open', mock.mock_open(read_data=b'invalid toml {'))
    @mock.patch('os.path.exists', return_value=True)
    def test_invalid_toml_syntax(self, mock_exists):
        """Test when config.toml has invalid TOML syntax."""
        valid, reason = runpod_mod.RunPod._check_runpod_credentials()

        assert valid is False
        assert 'not a valid TOML file' in reason

    @mock.patch('builtins.open', mock.mock_open(read_data=b'[other]\nkey = "value"'))
    @mock.patch('os.path.exists', return_value=True)
    def test_missing_default_profile(self, mock_exists):
        """Test when default profile is missing."""
        valid, reason = runpod_mod.RunPod._check_runpod_credentials()

        assert valid is False
        assert 'missing default profile' in reason

    @mock.patch('builtins.open',
                mock.mock_open(read_data=b'[default]\nother_key = "value"'))
    @mock.patch('os.path.exists', return_value=True)
    def test_missing_api_key_field(self, mock_exists):
        """Test when api_key field is missing."""
        valid, reason = runpod_mod.RunPod._check_runpod_credentials()

        assert valid is False
        assert 'missing api_key' in reason

    @mock.patch('builtins.open',
                mock.mock_open(read_data=b'[default]\napi_key = "test-key-123"'))
    @mock.patch('os.path.exists', return_value=True)
    def test_valid_credentials(self, mock_exists):
        """Test with valid credentials."""
        valid, reason = runpod_mod.RunPod._check_runpod_credentials()

        assert valid is True
        assert reason is None


class TestRunPodVolumeValidation:
    """Test RunPod volume name validation."""

    def test_valid_short_name(self):
        """Test valid volume name (short)."""
        valid, reason = runpod_mod.RunPod.is_volume_name_valid('my-volume')

        assert valid is True
        assert reason is None

    def test_valid_max_length_name(self):
        """Test volume name at exactly 30 chars (boundary)."""
        name = 'a' * 30  # Exactly 30 characters
        valid, reason = runpod_mod.RunPod.is_volume_name_valid(name)

        assert valid is True
        assert reason is None

    def test_invalid_too_long(self):
        """Test volume name exceeding 30 chars."""
        name = 'a' * 31  # 31 characters
        valid, reason = runpod_mod.RunPod.is_volume_name_valid(name)

        assert valid is False
        assert 'exceeds' in reason
        assert '30' in reason


class TestRunPodInstanceValidation:
    """Test RunPod instance type validation."""

    @mock.patch('sky.catalog.instance_type_exists')
    def test_valid_instance_type(self, mock_exists):
        """Test with valid instance type."""
        mock_exists.return_value = True
        cloud = runpod_mod.RunPod()

        result = cloud.instance_type_exists('1x_RTX5090_SECURE')

        assert result is True
        mock_exists.assert_called_once_with('1x_RTX5090_SECURE', 'runpod')

    @mock.patch('sky.catalog.instance_type_exists')
    def test_invalid_instance_type(self, mock_exists):
        """Test with invalid instance type."""
        mock_exists.return_value = False
        cloud = runpod_mod.RunPod()

        result = cloud.instance_type_exists('invalid-instance')

        assert result is False
        mock_exists.assert_called_once_with('invalid-instance', 'runpod')


class TestRunPodInstanceTypeParsing:
    """Test RunPod instance type parsing for availability checks."""

    def test_parse_simple_secure_instance(self):
        """Test parsing simple secure instance type."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            '1x_RTX5090_SECURE')

        assert result == {'gpu_id': 'RTX5090', 'gpu_count': 1}

    def test_parse_multi_gpu_instance(self):
        """Test parsing multi-GPU instance type."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            '4x_H100_SXM')

        assert result == {'gpu_id': 'H100-SXM', 'gpu_count': 4}

    def test_parse_complex_gpu_name(self):
        """Test parsing GPU with complex name (multiple parts)."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            '2x_A100_80GB_SXM_SECURE')

        assert result == {'gpu_id': 'A100-80GB-SXM', 'gpu_count': 2}

    def test_parse_community_instance(self):
        """Test parsing community (non-secure) instance type."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            '1x_RTX4090_COMMUNITY')

        assert result == {'gpu_id': 'RTX4090', 'gpu_count': 1}

    def test_parse_invalid_format_no_x(self):
        """Test parsing invalid format (missing 'x' in count)."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            '1_RTX5090_SECURE')

        assert result is None

    def test_parse_invalid_format_non_numeric_count(self):
        """Test parsing invalid format (non-numeric count)."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            'ax_RTX5090_SECURE')

        assert result is None

    def test_parse_invalid_format_too_few_parts(self):
        """Test parsing invalid format (too few parts)."""
        result = runpod_mod.RunPod._parse_instance_type_for_availability(
            '1x')

        assert result is None


class TestRunPodAvailabilityCheck:
    """Test RunPod availability checking via check_quota_available."""

    @pytest.fixture
    def mock_resources(self):
        """Create mock resources for testing."""
        # Create mock with spec_set to avoid assert_* special handling
        resources = mock.Mock(spec=['instance_type', 'region', 'assert_launchable'])
        resources.instance_type = '1x_RTX5090_SECURE'
        resources.region = 'US-CA-1'
        resources.assert_launchable = mock.Mock(return_value=resources)
        return resources

    @mock.patch('runpod.api.graphql.run_graphql_query')
    def test_stock_available_high(self, mock_graphql, mock_resources):
        """Test when GPU is in stock with High status."""
        mock_graphql.return_value = {
            'data': {
                'gpuTypes': [{
                    'id': 'RTX5090',
                    'displayName': 'RTX 5090',
                    'lowestPrice': {
                        'stockStatus': 'High',
                        'availableGpuCounts': [1, 2, 4, 8]
                    }
                }]
            }
        }

        result = runpod_mod.RunPod.check_quota_available(mock_resources)

        assert result is True

    @mock.patch('runpod.api.graphql.run_graphql_query')
    def test_stock_completely_unavailable(self, mock_graphql, mock_resources):
        """Test when GPU is completely out of stock."""
        mock_graphql.return_value = {
            'data': {
                'gpuTypes': [{
                    'id': 'RTX5090',
                    'displayName': 'RTX 5090',
                    'lowestPrice': {
                        'stockStatus': 'None',
                        'availableGpuCounts': []
                    }
                }]
            }
        }

        result = runpod_mod.RunPod.check_quota_available(mock_resources)

        assert result is False

    @mock.patch('runpod.api.graphql.run_graphql_query')
    def test_requested_count_not_available(self, mock_graphql, mock_resources):
        """Test when requested GPU count is not available."""
        # Request 4 GPUs but only 1 and 2 are available
        mock_resources.instance_type = '4x_RTX5090_SECURE'

        mock_graphql.return_value = {
            'data': {
                'gpuTypes': [{
                    'id': 'RTX5090',
                    'lowestPrice': {
                        'stockStatus': 'Low',
                        'availableGpuCounts': [1, 2]  # 4 not in list
                    }
                }]
            }
        }

        result = runpod_mod.RunPod.check_quota_available(mock_resources)

        assert result is False

    @mock.patch('runpod.api.graphql.run_graphql_query')
    def test_graphql_error_returns_true(self, mock_graphql, mock_resources):
        """Test that GraphQL errors fail open (return True)."""
        mock_graphql.return_value = {
            'errors': [{'message': 'Some GraphQL error'}]
        }

        result = runpod_mod.RunPod.check_quota_available(mock_resources)

        assert result is True  # Fail open on errors

    @mock.patch('runpod.api.graphql.run_graphql_query')
    def test_api_exception_returns_true(self, mock_graphql, mock_resources):
        """Test that API exceptions fail open (return True)."""
        mock_graphql.side_effect = Exception('Network error')

        result = runpod_mod.RunPod.check_quota_available(mock_resources)

        assert result is True  # Fail open on exceptions

    @mock.patch('runpod.api.graphql.run_graphql_query')
    def test_empty_gpu_types_returns_true(self, mock_graphql, mock_resources):
        """Test that empty gpuTypes list fails open (return True)."""
        mock_graphql.return_value = {
            'data': {
                'gpuTypes': []
            }
        }

        result = runpod_mod.RunPod.check_quota_available(mock_resources)

        assert result is True  # Fail open when no GPU types found

    def test_unparseable_instance_type_returns_true(self):
        """Test that unparseable instance types fail open (return True)."""
        # Create mock with spec to avoid assert_* special handling
        resources = mock.Mock(spec=['instance_type', 'region', 'assert_launchable'])
        resources.instance_type = 'invalid_format'
        resources.region = 'US-CA-1'
        resources.assert_launchable = mock.Mock(return_value=resources)

        result = runpod_mod.RunPod.check_quota_available(resources)

        assert result is True  # Fail open when can't parse instance type
