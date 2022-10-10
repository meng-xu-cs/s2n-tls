# This script aims at eliminating the false positive cases in the reports as many as possible
# This script only suits the current result, in order to clean the result
# Idealistically we should add the cleaning inside the fuzzing process

import glob
import json


path = "./work/fuzz/survival"
origin_path = "./work/fuzz/mutation-points.json"
# open the above file
origin_file = open(origin_path, "r")
origin_json = json.load(origin_file)
print(origin_json)
cnt = 0
for survival in glob.glob(path+ "/**"):
    
    trace_file = survival + "/trace.json"
    with open(trace_file, "r") as file:
        content = json.load(file)
    # Step 1 filter out the higher-order cases
    if len(content) <= 1:
        continue
    
    # Disallow filp and filp
    
    if "action" in list(content[0]["package"].keys()):
       if content[0]["package"]["action"] == "flip":
           continue    
    # Disallow swap and swap
    # Disallow switch branch and switch branch
    # Disallow target to be the same as the original one
    # - disallow non-constant mutation repetition
    # -- we need to match the original json here, key:
    # -- instruction, function, rule
    
    # Create a rep vector
    repetition = []
    jump_flag = 0
    for item in origin_json:
        
        if(item["function"] == content[0]["function"] and 
            item["rule"] == content[0]["rule"] and 
            item["instruction"] == content[0]["instruction"] and
            len(content[0]["package"]) == 1            
        ):
        # Then check to see if there is repetition.
            repetition.append(item["origin_mutate"])
            for content_item in content:
                if len(content_item["package"]) >1:
                    break
                if content_item["package"]["repl"] in repetition:
                    jump_flag = 1
                    break 
                repetition.append(content_item["package"]["repl"])
                 

    if jump_flag == 1:
        continue
    #print(len(content))   
    cnt = cnt +1
    print(content)     
