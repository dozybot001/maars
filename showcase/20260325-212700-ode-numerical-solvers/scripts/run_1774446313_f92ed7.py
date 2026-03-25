import os
if os.path.exists('/workspace/output/vdp_refs/'):
    print(os.listdir('/workspace/output/vdp_refs/'))
else:
    print("Directory not found")
