"""Unit tests for catalog data fetchers with availability filtering.

Tests the conservative availability filtering logic for Lambda Cloud and RunPod.
"""
import tempfile
from unittest import mock

import pytest

from sky.catalog.data_fetchers import fetch_lambda_cloud
from sky.catalog.data_fetchers import fetch_runpod

# === Lambda Cloud Tests ===


class TestLambdaCloudFetcher:
    """Tests for ConservativeLambdaFetcher"""

    @pytest.fixture
    def mock_api_response(self):
        """Mock Lambda Cloud API response"""
        return {
            'data': {
                'gpu_1x_a100': {
                    'instance_type': {
                        'name': 'A100',
                        'gpu_count': 1,
                        'vcpus': 16,
                        'memory_gib': 117,
                        'price_cents_per_hour': 110,
                        'gpu_memory_gib': 40,
                    },
                    'regions_with_capacity_available': [
                        {
                            'name': 'us-east-1'
                        },
                        {
                            'name': 'us-west-1'
                        },
                    ]
                },
                'gpu_1x_h100': {
                    'instance_type': {
                        'name': 'H100',
                        'gpu_count': 1,
                        'vcpus': 20,
                        'memory_gib': 125,
                        'price_cents_per_hour': 199,
                        'gpu_memory_gib': 80,
                    },
                    'regions_with_capacity_available': []  # No availability
                },
            }
        }

    @pytest.fixture
    def fetcher_conservative(self):
        """Create conservative fetcher"""
        return fetch_lambda_cloud.ConservativeLambdaFetcher(api_key='test-key',
                                                            conservative=True)

    @pytest.fixture
    def fetcher_strict(self):
        """Create non-conservative fetcher"""
        return fetch_lambda_cloud.ConservativeLambdaFetcher(api_key='test-key',
                                                            conservative=False)

    def test_api_fetch_success(self, fetcher_conservative, mock_api_response):
        """Test successful API data fetching"""
        with mock.patch('requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            data = fetcher_conservative.fetch_api_data()

            assert 'data' in data
            assert 'gpu_1x_a100' in data['data']
            mock_get.assert_called_once()

    def test_api_fetch_failure(self, fetcher_conservative):
        """Test API fetch failure handling"""
        with mock.patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('API Error')

            with pytest.raises(Exception):
                fetcher_conservative.fetch_api_data()

    def test_conservative_mode_no_availability(self, fetcher_conservative):
        """Test conservative mode falls back to all regions when no
        availability data"""
        instance_info = {'regions_with_capacity_available': []}

        regions = fetcher_conservative.get_available_regions(
            instance_info, 'test-instance')

        # Should return all regions as fallback
        assert len(regions) == len(fetch_lambda_cloud.ALL_REGIONS)
        region_names = [r['name'] for r in regions]
        assert 'us-east-1' in region_names
        assert 'us-west-1' in region_names

    def test_conservative_mode_single_region(self, fetcher_conservative):
        """Test conservative mode with single region (warns but keeps)"""
        instance_info = {
            'regions_with_capacity_available': [{
                'name': 'us-east-1'
            }]
        }

        regions = fetcher_conservative.get_available_regions(
            instance_info, 'test-instance')

        # Should keep the single region
        assert len(regions) == 1
        assert regions[0]['name'] == 'us-east-1'

    def test_conservative_mode_all_regions(self, fetcher_conservative):
        """Test conservative mode when all regions are available"""
        all_region_dicts = [{'name': r} for r in fetch_lambda_cloud.ALL_REGIONS]
        instance_info = {'regions_with_capacity_available': all_region_dicts}

        regions = fetcher_conservative.get_available_regions(
            instance_info, 'test-instance')

        # Should proceed with all regions (warns but doesn't fail)
        assert len(regions) == len(fetch_lambda_cloud.ALL_REGIONS)

    def test_strict_mode_no_availability(self, fetcher_strict):
        """Test non-conservative mode skips instances with no availability"""
        instance_info = {'regions_with_capacity_available': []}

        regions = fetcher_strict.get_available_regions(instance_info,
                                                       'test-instance')

        # Should return empty list
        assert len(regions) == 0

    def test_strict_mode_with_availability(self, fetcher_strict):
        """Test non-conservative mode uses API data as-is"""
        instance_info = {
            'regions_with_capacity_available': [
                {
                    'name': 'us-east-1'
                },
                {
                    'name': 'us-west-1'
                },
            ]
        }

        regions = fetcher_strict.get_available_regions(instance_info,
                                                       'test-instance')

        assert len(regions) == 2
        assert regions[0]['name'] == 'us-east-1'
        assert regions[1]['name'] == 'us-west-1'

    def test_generate_catalog_conservative(self, fetcher_conservative,
                                           mock_api_response):
        """Test catalog generation in conservative mode"""
        rows = fetcher_conservative.generate_catalog(mock_api_response)

        # Should have rows for A100 (2 regions) + H100 (all regions fallback)
        # A100: 2 regions, H100: ~12 regions fallback
        assert len(rows) > 0

        # Check A100 rows
        a100_rows = [r for r in rows if r[0] == 'gpu_1x_a100']
        assert len(a100_rows) == 2  # 2 available regions

        # Check H100 rows (should fallback to all regions)
        h100_rows = [r for r in rows if r[0] == 'gpu_1x_h100']
        assert len(h100_rows) == len(fetch_lambda_cloud.ALL_REGIONS)

    def test_generate_catalog_strict(self, fetcher_strict, mock_api_response):
        """Test catalog generation in non-conservative mode"""
        rows = fetcher_strict.generate_catalog(mock_api_response)

        # Should only have A100 rows (H100 has no availability)
        a100_rows = [r for r in rows if r[0] == 'gpu_1x_a100']
        assert len(a100_rows) == 2

        h100_rows = [r for r in rows if r[0] == 'gpu_1x_h100']
        assert len(h100_rows) == 0  # Skipped due to no availability

    def test_catalog_row_format(self, fetcher_conservative):
        """Test catalog row format matches expected columns"""
        api_data = {
            'data': {
                'gpu_1x_rtx5090': {
                    'instance_type': {
                        'name': 'RTX5090',
                        'gpu_count': 1,
                        'vcpus': 8,
                        'memory_gib': 32,
                        'price_cents_per_hour': 50,
                        'gpu_memory_gib': 24,
                    },
                    'regions_with_capacity_available': [{
                        'name': 'us-east-1'
                    }]
                }
            }
        }

        rows = fetcher_conservative.generate_catalog(api_data)
        assert len(rows) == 1

        row = rows[0]
        assert row[0] == 'gpu_1x_rtx5090'  # InstanceType
        assert row[1] == 'RTX5090'  # AcceleratorName
        assert row[2] == '1'  # AcceleratorCount
        assert row[3] == '8'  # vCPUs
        assert row[4] == '32'  # MemoryGiB
        assert row[5] == '0.50'  # Price
        assert row[6] == 'us-east-1'  # Region
        assert 'RTX5090' in row[7]  # GpuInfo (JSON)
        assert row[8] == ''  # SpotPrice

    def test_validation_minimum_rows(self, fetcher_conservative):
        """Test validation fails with too few rows"""
        rows = [['type1', 'GPU', '1', '8', '32', '1.00', 'us-east-1', '{}', '']]

        # Should fail with only 1 row (minimum is 50)
        assert not fetcher_conservative.validate_catalog(rows)

    def test_validation_duplicates(self, fetcher_conservative):
        """Test validation catches duplicate instance-region pairs"""
        # Create 60 rows (meets minimum)
        rows = []
        for _ in range(60):
            rows.append(
                ['type1', 'GPU', '1', '8', '32', '1.00', 'us-east-1', '{}', ''])

        # All rows are duplicates (same instance_type and region)
        assert not fetcher_conservative.validate_catalog(rows)

    def test_validation_price_sanity(self, fetcher_conservative):
        """Test validation with suspicious prices"""
        # Create 60 valid unique rows
        rows = []
        for i in range(60):
            rows.append([
                f'type{i}',
                'GPU',
                '1',
                '8',
                '32',
                '150.00',  # High price
                'us-east-1',
                '{}',
                ''
            ])

        # Should pass (just warns on high prices)
        # All instances are unique
        assert fetcher_conservative.validate_catalog(rows)

    def test_validation_success(self, fetcher_conservative):
        """Test validation passes with valid catalog"""
        # Create 60 valid unique rows
        rows = []
        for i in range(60):
            rows.append([
                f'type{i % 30}', 'GPU', '1', '8', '32', '1.50',
                f'region{i // 30}', '{}', ''
            ])

        assert fetcher_conservative.validate_catalog(rows)

    def test_csv_writing(self, fetcher_conservative):
        """Test CSV file writing"""
        rows = []
        for i in range(60):
            rows.append([
                f'type{i}', 'GPU', '1', '8', '32', '1.50', 'us-east-1', '{}', ''
            ])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = f'{tmpdir}/test.csv'
            fetcher_conservative.write_csv(rows, output_path)

            # Verify file exists and has correct number of lines
            with open(output_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Header + 60 rows
                assert len(lines) == 61


# === RunPod Tests ===


class TestRunPodFetcher:
    """Tests for ConservativeRunPodFetcher"""

    @pytest.fixture
    def mock_gpu_types(self):
        """Mock RunPod GPU types response"""
        return [{
            'id': 'NVIDIA RTX 5090',
            'displayName': 'RTX 5090',
            'memoryInGb': 24,
            'secureCloud': True,
            'communityCloud': True,
            'securePrice': 0.50,
            'communityPrice': 0.40,
            'lowestPrice': {
                'minimumBidPrice': 0.30,
                'uninterruptablePrice': 0.50,
            }
        }, {
            'id': 'NVIDIA A100',
            'displayName': 'A100',
            'memoryInGb': 40,
            'secureCloud': True,
            'communityCloud': False,
            'securePrice': 1.10,
            'communityPrice': None,
            'lowestPrice': {
                'minimumBidPrice': 0.80,
                'uninterruptablePrice': 1.10,
            }
        }]

    @pytest.fixture
    def fetcher(self):
        """Create RunPod fetcher"""
        return fetch_runpod.ConservativeRunPodFetcher(api_key='test-key',
                                                      conservative=True)

    def test_fetch_gpu_types_success(self, fetcher, mock_gpu_types):
        """Test successful GPU types fetching"""
        with mock.patch('requests.post') as mock_post:
            mock_response = mock.Mock()
            mock_response.json.return_value = {
                'data': {
                    'gpuTypes': mock_gpu_types
                }
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            gpu_types = fetcher.fetch_gpu_types()

            assert len(gpu_types) == 2
            assert gpu_types[0]['displayName'] == 'RTX 5090'
            assert gpu_types[1]['displayName'] == 'A100'
            mock_post.assert_called_once()

    def test_fetch_gpu_types_failure(self, fetcher):
        """Test GPU types fetch failure handling"""
        with mock.patch('requests.post') as mock_post:
            mock_post.side_effect = Exception('API Error')

            with pytest.raises(Exception):
                fetcher.fetch_gpu_types()

    def test_fetch_availability_conservative(self, fetcher):
        """Test availability fetching in conservative mode returns all
        regions"""
        regions = fetcher.fetch_availability('test-gpu-id')

        # Conservative mode should return all regions
        assert len(regions) == len(fetch_runpod.ALL_REGIONS)
        assert 'US-CA-1' in regions
        assert 'EU-RO-1' in regions

    def test_generate_catalog(self, fetcher, mock_gpu_types):
        """Test catalog generation from GPU types"""
        rows = fetcher.generate_catalog(mock_gpu_types)

        # Should have rows for each GPU type × GPU counts × regions
        # 2 GPU types × 4 counts (1,2,4,8) × 9 regions = 72 rows
        expected_rows = 2 * 4 * len(fetch_runpod.ALL_REGIONS)
        assert len(rows) == expected_rows

        # Check RTX 5090 single GPU rows
        rtx5090_1x = [r for r in rows if r[0] == 'RTX 5090-1x']
        assert len(rtx5090_1x) == len(fetch_runpod.ALL_REGIONS)

        # Check A100 8x GPU rows
        a100_8x = [r for r in rows if r[0] == 'A100-8x']
        assert len(a100_8x) == len(fetch_runpod.ALL_REGIONS)

    def test_catalog_row_format_runpod(self, fetcher):
        """Test RunPod catalog row format"""
        gpu_types = [{
            'id': 'NVIDIA H100',
            'displayName': 'H100',
            'memoryInGb': 80,
            'secureCloud': True,
            'communityCloud': False,
            'securePrice': 2.00,
            'communityPrice': None,
            'lowestPrice': {
                'minimumBidPrice': 1.50,
                'uninterruptablePrice': 2.00,
            }
        }]

        rows = fetcher.generate_catalog(gpu_types)

        # Find a 1x GPU row
        h100_1x_rows = [r for r in rows if r[0] == 'H100-1x']
        assert len(h100_1x_rows) > 0

        row = h100_1x_rows[0]
        assert row[0] == 'H100-1x'  # InstanceType
        assert row[1] == 'H100'  # AcceleratorName
        assert row[2] == '1'  # AcceleratorCount
        assert row[3] == '8'  # vCPUs (8 per GPU)
        assert row[4] == '30'  # MemoryGiB (30 per GPU)
        assert row[5] == '2.00'  # Price
        assert row[6] in fetch_runpod.ALL_REGIONS  # Region
        assert 'H100' in row[7]  # GpuInfo
        assert row[8] == '1.50'  # SpotPrice

    def test_catalog_scaling_by_gpu_count(self, fetcher):
        """Test that resources scale correctly with GPU count"""
        gpu_types = [{
            'id': 'test',
            'displayName': 'TestGPU',
            'memoryInGb': 16,
            'secureCloud': True,
            'communityCloud': False,
            'securePrice': 1.00,
            'communityPrice': None,
            'lowestPrice': {
                'minimumBidPrice': 0.80,
                'uninterruptablePrice': 1.00,
            }
        }]

        rows = fetcher.generate_catalog(gpu_types)

        # Check 1x
        row_1x = [r for r in rows if r[2] == '1'][0]
        assert row_1x[3] == '8'  # 8 vCPUs
        assert row_1x[4] == '30'  # 30 GB memory
        assert row_1x[5] == '1.00'  # $1.00/hr

        # Check 4x
        row_4x = [r for r in rows if r[2] == '4'][0]
        assert row_4x[3] == '32'  # 8 * 4 = 32 vCPUs
        assert row_4x[4] == '120'  # 30 * 4 = 120 GB memory
        assert row_4x[5] == '4.00'  # $1.00 * 4 = $4.00/hr

    def test_validation_minimum_rows_runpod(self, fetcher):
        """Test RunPod validation with minimum row requirement"""
        # Too few rows
        rows = [[
            'type1', 'GPU', '1', '8', '30', '1.00', 'US-CA-1', '{}', '0.80'
        ]]

        assert not fetcher.validate_catalog(rows)

        # Enough rows with unique combinations (should pass)
        rows = []
        for i in range(35):
            rows.append([
                f'type{i}', 'GPU', '1', '8', '30', '1.00', 'US-CA-1', '{}',
                '0.80'
            ])

        # Should pass - all unique instance_type + region pairs
        assert fetcher.validate_catalog(rows)

        # Now test with actual duplicates (should fail)
        rows_with_duplicates = []
        for i in range(35):
            # Create duplicates by using same instance type and region
            rows_with_duplicates.append([
                'same-type', 'GPU', '1', '8', '30', '1.00', 'US-CA-1', '{}',
                '0.80'
            ])

        # Should fail due to duplicates
        assert not fetcher.validate_catalog(rows_with_duplicates)

    def test_validation_success_runpod(self, fetcher):
        """Test RunPod validation passes with valid catalog"""
        rows = []
        for i in range(40):
            rows.append([
                f'type{i % 20}', 'GPU', '1', '8', '30', '1.50',
                f'region{i // 20}', '{}', '1.00'
            ])

        assert fetcher.validate_catalog(rows)


# === Integration Tests ===


class TestDataFetcherIntegration:
    """Integration tests for data fetchers"""

    def test_lambda_end_to_end_conservative(self):
        """Test Lambda fetcher end-to-end in conservative mode"""
        fetcher = fetch_lambda_cloud.ConservativeLambdaFetcher(
            api_key='test-key', conservative=True)

        mock_response = {
            'data': {
                'gpu_1x_test': {
                    'instance_type': {
                        'name': 'TestGPU',
                        'gpu_count': 1,
                        'vcpus': 8,
                        'memory_gib': 32,
                        'price_cents_per_hour': 100,
                        'gpu_memory_gib': 24,
                    },
                    'regions_with_capacity_available': []  # No availability
                }
            }
        }

        # Generate enough instances to pass validation
        for i in range(60):
            mock_response['data'][f'gpu_1x_test{i}'] = {
                'instance_type': {
                    'name': f'GPU{i}',
                    'gpu_count': 1,
                    'vcpus': 8,
                    'memory_gib': 32,
                    'price_cents_per_hour': 100 + i,
                    'gpu_memory_gib': 24,
                },
                'regions_with_capacity_available': [
                    {
                        'name': 'us-east-1'
                    },
                    {
                        'name': 'us-west-1'
                    },
                ]
            }

        rows = fetcher.generate_catalog(mock_response)

        # Should have fallback regions for instances without availability
        assert len(rows) > 50
        assert fetcher.validate_catalog(rows)

    def test_runpod_end_to_end(self):
        """Test RunPod fetcher end-to-end"""
        fetcher = fetch_runpod.ConservativeRunPodFetcher(api_key='test-key',
                                                         conservative=True)

        mock_gpu_types = []
        for i in range(10):
            mock_gpu_types.append({
                'id': f'gpu-{i}',
                'displayName': f'GPU{i}',
                'memoryInGb': 24,
                'secureCloud': True,
                'communityCloud': True,
                'securePrice': 1.00 + (i * 0.1),
                'communityPrice': 0.80 + (i * 0.1),
                'lowestPrice': {
                    'minimumBidPrice': 0.60 + (i * 0.1),
                    'uninterruptablePrice': 1.00 + (i * 0.1),
                }
            })

        rows = fetcher.generate_catalog(mock_gpu_types)

        # Should have rows for all GPU types × counts × regions
        assert len(rows) > 30
        assert fetcher.validate_catalog(rows)
