import json
import os

input_file_path = "../../andrew@openmined.org/app_pipelines/adder/inputs/data.json"
output_file_path = "../../andrew@openmined.org/app_pipelines/adder/done/data.json"

if os.path.exists(input_file_path):
    with open(input_file_path, 'r') as f:
        data = json.load(f)

    data['datum'] += 1

    with open(output_file_path, 'w') as f:
        json.dump(data, f)

    os.remove(input_file_path)
else:
    print(f"Input file {input_file_path} does not exist.")