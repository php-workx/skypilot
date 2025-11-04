"""Unit tests for catalog data fetchers.

Tests the actual function-based implementations of Lambda Cloud and RunPod fetchers.
"""
import csv
import json
import tempfile
from unittest import mock

import pytest

from sky.catalog.data_fetchers import fetch_lambda_cloud
from sky.catalog.data_fetchers import fetch_runpod

# === Lambda Cloud Tests ===


class TestLambdaCloudFetcher:
    """Tests for fetch_lambda_cloud module"""

    @pytest.fixture
    def mock_api_response(self):
        """Mock Lambda Cloud API response"""
        return {
            'data': {
                'gpu_1x_a100': {
                    'instance_type': {
                        'specs': {
                            'vcpus': 16,
                            'memory_gib': 117
                        },
                        'price_cents_per_hour': 110,
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
                        'specs': {
                            'vcpus': 20,
                            'memory_gib': 125
                        },
                        'price_cents_per_hour': 199,
                    },
                    'regions_with_capacity_available': []  # No availability
                },
            }
        }

    def test_name_to_gpu_and_cnt_standard(self):
        """Test parsing standard GPU instance names"""
        gpu, cnt = fetch_lambda_cloud.name_to_gpu_and_cnt('gpu_1x_a100')
        assert gpu == 'A100'
        assert cnt == 1

        gpu, cnt = fetch_lambda_cloud.name_to_gpu_and_cnt('gpu_8x_h100_sxm')
        assert gpu == 'H100'
        assert cnt == 8

    def test_name_to_gpu_and_cnt_special_case(self):
        """Test parsing special case A100-80GB instance"""
        gpu, cnt = fetch_lambda_cloud.name_to_gpu_and_cnt(
            'gpu_8x_a100_80gb_sxm4')
        assert gpu == 'A100-80GB'
        assert cnt == 8

    def test_name_to_gpu_and_cnt_general(self):
        """Test parsing GENERAL instance returns None"""
        result = fetch_lambda_cloud.name_to_gpu_and_cnt('gpu_1x_general')
        assert result is None

    def test_create_catalog_with_filter(self, mock_api_response):
        """Test catalog creation with availability filtering"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                         delete=False) as f:
            output_path = f.name

        with mock.patch('requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            fetch_lambda_cloud.create_catalog(api_key='test-key',
                                              output_path=output_path,
                                              filter_available=True)

        # Read and verify CSV
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + A100 (2 regions) + H100 (0 regions with filter) = 3 rows
        assert len(rows) == 3  # header + 2 A100 rows
        assert rows[0][0] == 'InstanceType'  # Header

        # Check A100 rows
        a100_rows = [r for r in rows[1:] if r[0] == 'gpu_1x_a100']
        assert len(a100_rows) == 2
        assert a100_rows[0][6] in ['us-east-1', 'us-west-1']

    def test_create_catalog_without_filter(self, mock_api_response):
        """Test catalog creation without filtering (all regions)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                         delete=False) as f:
            output_path = f.name

        with mock.patch('requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            fetch_lambda_cloud.create_catalog(api_key='test-key',
                                              output_path=output_path,
                                              filter_available=False)

        # Read and verify CSV
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        # With filter_available=False, all instances get all regions
        # 2 instances × 17 regions = 34 data rows + 1 header = 35 total
        expected_rows = 1 + (2 * len(fetch_lambda_cloud.REGIONS))
        assert len(rows) == expected_rows

    def test_catalog_row_format(self, mock_api_response):
        """Test catalog CSV row format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                         delete=False) as f:
            output_path = f.name

        with mock.patch('requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            fetch_lambda_cloud.create_catalog(api_key='test-key',
                                              output_path=output_path,
                                              filter_available=True)

        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check header
        assert rows[0] == [
            'InstanceType', 'AcceleratorName', 'AcceleratorCount', 'vCPUs',
            'MemoryGiB', 'Price', 'Region', 'GpuInfo', 'SpotPrice'
        ]

        # Check data row format
        data_row = rows[1]
        assert data_row[0] == 'gpu_1x_a100'  # InstanceType
        assert data_row[1] == 'A100'  # AcceleratorName
        assert data_row[2] == '1.0'  # AcceleratorCount
        assert data_row[3] == '16.0'  # vCPUs
        assert data_row[4] == '117.0'  # MemoryGiB
        assert data_row[5] == '1.1'  # Price (110 cents = $1.10)
        assert data_row[6] in ['us-east-1', 'us-west-1']  # Region
        assert 'A100' in data_row[7]  # GpuInfo contains GPU name
        assert data_row[8] == ''  # SpotPrice (empty for Lambda)

    def test_gpu_info_json_format(self):
        """Test that GPU info is properly formatted JSON"""
        mock_response = {
            'data': {
                'gpu_1x_rtx6000': {
                    'instance_type': {
                        'specs': {
                            'vcpus': 8,
                            'memory_gib': 32
                        },
                        'price_cents_per_hour': 50,
                    },
                    'regions_with_capacity_available': [{
                        'name': 'us-east-1'
                    }]
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                         delete=False) as f:
            output_path = f.name

        with mock.patch('requests.get') as mock_get:
            mock_resp = mock.Mock()
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            fetch_lambda_cloud.create_catalog(api_key='test-key',
                                              output_path=output_path,
                                              filter_available=True)

        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        gpu_info = rows[1][7]
        # Convert single quotes back to double quotes to parse as JSON
        gpu_info_dict = json.loads(gpu_info.replace("'", '"'))

        assert 'Gpus' in gpu_info_dict
        assert len(gpu_info_dict['Gpus']) == 1
        assert gpu_info_dict['Gpus'][0]['Name'] == 'RTX6000'
        assert gpu_info_dict['Gpus'][0]['Count'] == 1.0
        assert 'MemoryInfo' in gpu_info_dict['Gpus'][0]


# === RunPod Tests ===


class TestRunPodFetcher:
    """Tests for fetch_runpod module"""

    def test_format_gpu_name_standard(self):
        """Test GPU name formatting for standard GPUs"""
        gpu_type = {'displayName': 'RTX 5090', 'manufacturer': 'NVIDIA'}
        name = fetch_runpod.format_gpu_name(gpu_type)
        assert name == 'RTX5090'

        gpu_type = {'displayName': 'H100 SXM', 'manufacturer': 'NVIDIA'}
        name = fetch_runpod.format_gpu_name(gpu_type)
        assert name == 'H100-SXM'

    def test_format_gpu_name_rtx_pro(self):
        """Test GPU name formatting for RTX PRO series"""
        gpu_type = {'displayName': 'RTX PRO 6000', 'manufacturer': 'NVIDIA'}
        name = fetch_runpod.format_gpu_name(gpu_type)
        assert name == 'RTXPRO6000'

    def test_format_gpu_name_overrides(self):
        """Test GPU name overrides for backwards compatibility"""
        # A100-PCIe should be overridden to A100-80GB
        gpu_type = {'displayName': 'A100 PCIe', 'manufacturer': 'NVIDIA'}
        name = fetch_runpod.format_gpu_name(gpu_type)
        assert name == 'A100-80GB'

    def test_format_price(self):
        """Test price formatting to 2 decimal places"""
        assert fetch_runpod.format_price(1.234) == 1.23
        assert fetch_runpod.format_price(0.999) == 1.0
        assert fetch_runpod.format_price(1.5) == 1.5

    def test_get_gpu_info_with_defaults(self):
        """Test GPU info extraction using default values"""
        gpu_type = {
            'displayName': 'H100',
            'manufacturer': 'NVIDIA',
            'memoryInGb': 80,
            'lowestPrice': {
                'minVcpu': 20,
                'minMemory': 200
            }
        }

        # H100 is in DEFAULT_GPU_INFO
        info = fetch_runpod.get_gpu_info('H100', gpu_type, gpu_count=2)

        assert info is not None
        # Default vCPUs for H100 is 16, scaled by count 2 = 32
        assert info['vCPUs'] == 32.0
        # Default memory for H100 is 176, scaled by count 2 = 352
        assert info['MemoryGiB'] == 352.0
        assert 'GpuInfo' in info
        assert 'H100' in info['GpuInfo']

    def test_get_gpu_info_without_defaults(self):
        """Test GPU info extraction falling back to API values"""
        gpu_type = {
            'displayName': 'UnknownGPU',
            'manufacturer': 'NVIDIA',
            'memoryInGb': 24,
            'lowestPrice': {
                'minVcpu': 8,
                'minMemory': 30
            }
        }

        info = fetch_runpod.get_gpu_info('UnknownGPU', gpu_type, gpu_count=1)

        assert info is not None
        # Falls back to API values
        assert info['vCPUs'] == 8.0
        assert info['MemoryGiB'] == 30.0

    def test_get_gpu_info_invalid_values(self):
        """Test GPU info returns None for invalid data"""
        # Invalid vCPU (negative)
        gpu_type = {
            'displayName': 'TestGPU',
            'manufacturer': 'NVIDIA',
            'memoryInGb': 24,
            'lowestPrice': {
                'minVcpu': -1,
                'minMemory': 30
            }
        }
        info = fetch_runpod.get_gpu_info('TestGPU', gpu_type, gpu_count=1)
        assert info is None

        # Invalid memory (zero)
        gpu_type['lowestPrice']['minVcpu'] = 8
        gpu_type['lowestPrice']['minMemory'] = 0
        info = fetch_runpod.get_gpu_info('TestGPU', gpu_type, gpu_count=1)
        assert info is None

    def test_region_zones_mapping(self):
        """Test that region-zone mapping is complete"""
        assert 'US' in fetch_runpod.REGION_ZONES
        assert 'CA' in fetch_runpod.REGION_ZONES
        assert 'EU' not in fetch_runpod.REGION_ZONES  # EU prefix only
        assert 'RO' in fetch_runpod.REGION_ZONES
        assert 'SE' in fetch_runpod.REGION_ZONES

        # Check US has multiple zones
        assert len(fetch_runpod.REGION_ZONES['US']) > 5

    def test_default_gpu_info_completeness(self):
        """Test that DEFAULT_GPU_INFO has required fields"""
        for gpu_name, info in fetch_runpod.DEFAULT_GPU_INFO.items():
            assert 'vcpus' in info, f"{gpu_name} missing vcpus"
            assert 'memory' in info, f"{gpu_name} missing memory"
            assert 'max_count' in info, f"{gpu_name} missing max_count"

            # Values should be positive
            assert info['vcpus'] > 0, f"{gpu_name} has invalid vcpus"
            assert info['memory'] > 0, f"{gpu_name} has invalid memory"
            assert info['max_count'] > 0, f"{gpu_name} has invalid max_count"

    def test_gpu_name_overrides_exist(self):
        """Test that GPU name overrides are applied correctly"""
        # These are the overrides that should exist
        expected_overrides = {
            'A100-PCIe': 'A100-80GB',
            'A100-SXM': 'A100-80GB-SXM',
            'H100-PCIe': 'H100',
        }

        for original, expected in expected_overrides.items():
            assert original in fetch_runpod.GPU_NAME_OVERRIDES
            assert fetch_runpod.GPU_NAME_OVERRIDES[original] == expected


# === Integration-Style Tests ===


class TestDataFetcherConstants:
    """Test that module constants are properly defined"""

    def test_lambda_regions_defined(self):
        """Test Lambda Cloud regions list"""
        assert isinstance(fetch_lambda_cloud.REGIONS, list)
        assert len(fetch_lambda_cloud.REGIONS) > 0
        assert 'us-east-1' in fetch_lambda_cloud.REGIONS
        assert 'us-west-1' in fetch_lambda_cloud.REGIONS

    def test_lambda_gpu_memory_defined(self):
        """Test Lambda Cloud GPU memory mappings"""
        assert isinstance(fetch_lambda_cloud.GPU_TO_MEMORY, dict)
        assert 'A100' in fetch_lambda_cloud.GPU_TO_MEMORY
        assert 'H100' in fetch_lambda_cloud.GPU_TO_MEMORY
        assert fetch_lambda_cloud.GPU_TO_MEMORY['A100'] == 40960
        assert fetch_lambda_cloud.GPU_TO_MEMORY['H100'] == 81920

    def test_lambda_endpoint_defined(self):
        """Test Lambda Cloud API endpoint"""
        assert isinstance(fetch_lambda_cloud.ENDPOINT, str)
        assert 'lambdalabs.com' in fetch_lambda_cloud.ENDPOINT
        assert fetch_lambda_cloud.ENDPOINT.startswith('https://')

    def test_runpod_constants_defined(self):
        """Test RunPod constants are properly defined"""
        assert isinstance(fetch_runpod.DEFAULT_GPU_INFO, dict)
        assert isinstance(fetch_runpod.GPU_NAME_OVERRIDES, dict)
        assert isinstance(fetch_runpod.REGION_ZONES, dict)
        assert isinstance(fetch_runpod.DEFAULT_MAX_GPUS, int)
        assert fetch_runpod.DEFAULT_MAX_GPUS == 8
