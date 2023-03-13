from jaypore_ci import jci

with jci.Pipeline() as p:
    p.job("Black", "black --check .")
