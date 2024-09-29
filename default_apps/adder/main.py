import json
import os

f = open("../../andrew@openmined.org/app_pipelines/adder/inputs/data.json",'r')
data = json.load(f)
f.close()

data['datum'] += 1

f = open("../../andrew@openmined.org/app_pipelines/adder/done/data.json",'w')
f.write(json.dumps(data))
f.close()

os.remove("../../andrew@openmined.org/app_pipelines/adder/inputs/data.json")