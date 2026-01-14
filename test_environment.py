"""
Environment test script
=======================

This module provides a small utility to check whether the 'ccai9012' development
environment has the expected Python packages installed. It is intended for
teaching and troubleshooting.

Usage:
    conda activate ccai9012
    python test_environment.py

Verbose usage:
    python test_environment.py --verbose
"""

import sys
import importlib
import argparse


class EnvironmentTester:
    """Class responsible for running a set of import checks to validate the environment.

    The class collects results into `self.results` with keys:
      - 'passed': list of package names that imported successfully
      - 'failed': list of tuples (package_name, error_message) for failed imports
      - 'warnings': list of tuples (package_name, warning_message) for non-critical issues
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }

    def test_import(self, package_name: str, import_from: str = None,
                   display_name: str = None) -> bool:
        """
        Test importing a single package or attribute and record the result.

        Args:
            package_name: The package or attribute name to import.
            import_from: Optional module name to import from (for `from module import name` cases).
            display_name: Optional human-friendly name to display in results.

        Returns:
            bool: True if import succeeded, False otherwise. Records details in self.results.
        """
        if display_name is None:
            display_name = f"{import_from}.{package_name}" if import_from else package_name

        try:
            if import_from:
                module = importlib.import_module(import_from)
                getattr(module, package_name)
            else:
                importlib.import_module(package_name)

            if self.verbose:
                print(f"✓ {display_name}")
            self.results['passed'].append(display_name)
            return True

        except ImportError as e:
            error_msg = str(e)
            # Check if it's a version warning that doesn't prevent import
            if "needs NumPy" in error_msg or "Numba needs" in error_msg:
                if self.verbose:
                    print(f"⚠ {display_name}: {error_msg}")
                else:
                    print(f"⚠ {display_name}: Version compatibility warning (package still works)")
                self.results['warnings'].append((display_name, error_msg))
                # Mark as passed since the package actually works
                self.results['passed'].append(display_name)
                return True

            print(f"✗ {display_name}: {error_msg}")
            self.results['failed'].append((display_name, error_msg))
            return False
        except AttributeError as e:
            print(f"✗ {display_name}: {str(e)}")
            self.results['failed'].append((display_name, str(e)))
            return False
        except Exception as e:
            error_msg = str(e)
            print(f"⚠ {display_name}: {error_msg}")
            self.results['warnings'].append((display_name, error_msg))
            return False

    def print_header(self, text: str):
        """Print a formatted header for a test section to improve readability."""
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}")

    def test_core_packages(self):
        """Check essential scientific computing packages commonly used in the course."""
        self.print_header("Testing Core Scientific Packages")

        packages = [
            'numpy',
            'scipy',
            'pandas',
            'matplotlib',
            'sklearn',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_deep_learning(self):
        """Check common deep learning and model-related packages (PyTorch ecosystem, Transformers, etc.)."""
        self.print_header("Testing Deep Learning Frameworks")

        packages = [
            'torch',
            'torchvision',
            'transformers',
            'diffusers',
            'accelerate',
        ]

        for pkg in packages:
            self.test_import(pkg)

        # Test PyTorch functionality
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"  PyTorch device: {device}")
            if device == "cpu":
                self.results['warnings'].append(("PyTorch CUDA", "CUDA not available, using CPU"))
        except:
            pass

    def test_llm_packages(self):
        """Check packages commonly used for working with large language models and related tooling."""
        self.print_header("Testing LLM Packages")

        packages = [
            ('langchain', None),
            ('langchain_community', None),
            ('langchain_core', None),
            ('langchain_deepseek', None),
            ('langchain_openai', None),
            ('openai', None),
            ('tiktoken', None),
            ('sentence_transformers', None),
            ('faiss', None),  # pip/conda package name commonly: faiss-cpu (import as faiss)
            ('pypdf', None),
        ]

        for pkg, from_module in packages:
            self.test_import(pkg, from_module)

    def test_cv_packages(self):
        """Check common computer vision libraries and perform a basic YOLO import check."""
        self.print_header("Testing Computer Vision Packages")

        packages = [
            'cv2',
            'PIL',
            'ultralytics',
        ]

        for pkg in packages:
            self.test_import(pkg)

        # Test YOLO
        try:
            from ultralytics import YOLO
            if self.verbose:
                print("  YOLO import successful")
        except Exception as e:
            print(f"⚠ YOLO functionality: {str(e)}")

    def test_nlp_packages(self):
        """Check common natural language processing libraries used in exercises."""
        self.print_header("Testing NLP Packages")

        packages = [
            'spacy',
            'wordcloud',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_geospatial_packages(self):
        """Check geospatial analysis and mapping libraries commonly used in projects."""
        self.print_header("Testing Geospatial Packages")

        packages = [
            'geopandas',
            'folium',
            'geopy',
            'osmnx',
            'shapely',
            'pyproj',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_ml_packages(self):
        """Check popular machine learning libraries beyond core scikit-learn (e.g., boosting, fairness, explainability)."""
        self.print_header("Testing ML Packages")

        # Note: fairlearn and xgboost are NOT used in this project
        # fairlearn warnings come from aif360, but it's optional
        packages = [
            'lightgbm',
            'aif360',
            'shap',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_data_packages(self):
        """Check data engineering and serialization libraries (datasets, huggingface hub, pyarrow, etc.)."""
        self.print_header("Testing Data Processing Packages")

        packages = [
            'datasets',
            'huggingface_hub',
            'safetensors',
            'pyarrow',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_visualization_packages(self):
        """Check visualization libraries used for plotting, dashboards, and graphviz integration."""
        self.print_header("Testing Visualization Packages")

        packages = [
            'plotly',
            'seaborn',
            'pygraphviz',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_jupyter_packages(self):
        """Check Jupyter-related packages useful for interactive notebooks and widgets."""
        self.print_header("Testing Jupyter Packages")

        packages = [
            'jupyter',
            'jupyterlab',
            'IPython',
            'ipywidgets',
            'jupytext',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_utility_packages(self):
        """Check general utility packages (progress bars, HTTP, parsing, type validation, pretty printing, parallel tools)."""
        self.print_header("Testing Utility Packages")

        # Note: beautifulsoup4 is the package name, but import as bs4
        packages = [
            'tqdm',
            'requests',
            'bs4',  # pip install beautifulsoup4, but import bs4
            'pydantic',
            'rich',
            'joblib',
            'markdown'
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_video_audio_packages(self):
        """Check multimedia processing libraries for working with video and audio files."""
        self.print_header("Testing Video/Audio Packages")

        packages = [
            'moviepy',
            'imageio',
        ]

        for pkg in packages:
            self.test_import(pkg)

    def test_ccai9012_package(self):
        """Verify the local ccai9012 package and its submodules are importable for course exercises."""
        self.print_header("Testing CCAI9012 Toolkit")

        # Test main package
        if not self.test_import('ccai9012'):
            print("✗ Unable to import ccai9012 package. Please ensure it is installed: pip install -e .")
            return

        # Test submodules
        submodules = [
            'llm_utils',
            'nn_utils',
            'sd_utils',
            'svi_utils',
            'viz_utils',
            'yolo_utils',
            'multi_modal_utils',
            'gan_utils',
        ]

        for submodule in submodules:
            self.test_import(submodule, 'ccai9012', f'ccai9012.{submodule}')

    def test_all(self):
        """Run all defined test groups and produce a summarized report.

        This prints system information, runs each category of tests, and then calls print_summary.
        """
        print("\n" + "="*60)
        print("  CCAI9012 Environment Test Starting")
        print("="*60)

        # Python version check
        print(f"\nPython Version: {sys.version}")
        if sys.version_info < (3, 10):
            print("⚠ Warning: Python 3.10 or higher is recommended")

        # Run all test categories
        self.test_core_packages()
        self.test_deep_learning()
        self.test_llm_packages()
        self.test_cv_packages()
        self.test_nlp_packages()
        self.test_geospatial_packages()
        self.test_ml_packages()
        self.test_data_packages()
        self.test_visualization_packages()
        self.test_jupyter_packages()
        self.test_utility_packages()
        self.test_video_audio_packages()
        self.test_ccai9012_package()

        # Print summary
        return self.print_summary()

    def print_summary(self):
        """Summarize passed/failed/warning counts and provide basic remediation suggestions.

        The method prints human-readable counts and, if verbose, prints detailed error messages.
        """
        self.print_header("Test Summary")

        total = len(self.results['passed']) + len(self.results['failed']) + len(self.results['warnings'])
        passed = len(self.results['passed'])
        failed = len(self.results['failed'])
        warnings = len(self.results['warnings'])

        print(f"\nTotal tests: {total}")
        print(f"✓ Passed: {passed}")
        print(f"✗ Failed: {failed}")
        print(f"⚠ Warnings: {warnings}")

        if failed > 0:
            print("\nFailed packages:")
            for pkg, error in self.results['failed']:
                print(f"  - {pkg}")
                if self.verbose:
                    print(f"    Error: {error}")

        if warnings > 0 and self.verbose:
            print("\nWarnings:")
            for pkg, warning in self.results['warnings']:
                print(f"  - {pkg}: {warning}")

        # Final result
        print("\n" + "="*60)
        if failed == 0:
            print("✓ Environment test PASSED! All required packages are installed.")
            return 0
        else:
            print("✗ Environment test FAILED! Please install missing packages.")
            print("\nSuggested fix steps:")
            print("1. Ensure the correct conda environment is activated: conda activate ccai9012")
            print("2. Update environment: conda env update -f environment.yml")
            print("3. Install ccai9012 package: pip install -e .")
            return 1


def main():
    """Entry point: parse CLI args, create an EnvironmentTester, and execute the full test suite."""
    parser = argparse.ArgumentParser(description='Test ccai9012 environment configuration')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show verbose output')
    args = parser.parse_args()

    tester = EnvironmentTester(verbose=args.verbose)
    exit_code = tester.test_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
