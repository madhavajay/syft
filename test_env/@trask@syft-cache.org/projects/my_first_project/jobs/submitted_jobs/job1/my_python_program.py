import syft as sy
import pandas as pd
import os

from code import compute_length

# project_home = sy.project_home
project_home = "/Users/atrask/Laboratory/test_syft_idea/"

df = pd.read_csv(project_home+'/trask-datasite.com/netflix-shows/netflix_titles.csv')

result = compute_length.run(df)


# andrew@openmined.org is going to get an email saying 
# "hey someone has created outputs for you!". and when they
# follow the instructions, they'll create a datasite
# and register that datasite with WHATEVER gateway/cache
# messaged them. so if they generate a key then they 
# can claim the 

# asks known gateways if they know about andrew@openminedd.org
# if now then uses known gateways to find this person through email
# and the response to that email can claim this output
andrews_datasite_path = sy.get_address("andrew@openmined.org")

os.makedirs(andrews_datasite_path, exist_ok=True)
f = open(andrews_datasite_path,'w')
f.write(result)
f.close()
