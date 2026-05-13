"""
Usage: python check.py <cfn_template>

Generates an estimates template, lets you fill it in, then runs the analysis.
"""
import sys
import os
from cloudcap.analyzer import Analyzer, AnalyzerResult
from cloudcap.aws import AWS, Regions, Account
from cloudcap import estimates as est


def load_template(path: str) -> AWS:
    aws = AWS()
    aws.add_deployment(Regions.us_east_1, Account("123")).from_cloudformation_template(path=path)
    return aws


def main():
    if len(sys.argv) < 2:
        print("Usage: python check.py <cfn_template>")
        sys.exit(1)

    cfn_path = sys.argv[1]
    estimates_path = cfn_path.replace(".yaml", ".estimates.yaml")

    print("=== Generating estimates template ===")
    aws = load_template(cfn_path)
    template = est.template_to_string(aws)
    print(template)

    with open(estimates_path, "w") as f:
        f.write(template)
    print(f"Saved to {estimates_path}")

    input("Fill in your estimates, then press Enter to run the analysis...")

    print("\n=== Running analysis ===")
    aws = load_template(cfn_path)
    analyzer = Analyzer(aws)
    analyzer.constrain()
    analyzer.add_estimates(est.load(estimates_path))
    result = analyzer.solve()

    if result == AnalyzerResult.PASS:
        print("✅ Pass")
    elif result == AnalyzerResult.REJECT:
        print("❌ Reject")
    else:
        print("⚠️ Solver returned unknown")


if __name__ == "__main__":
    main()
