import glob; import os
for f in glob.glob("/home/alucard/Downloads/AI Bot/backend/clones/alucard/data/*.txt"):
    content = open(f, "r").read()
    open(f, "w").write(content.replace("\t", " "))
