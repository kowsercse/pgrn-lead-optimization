Score_structure_quality should have 2 different branches. If it is an experimental structure, it should use the structure's resolution 
and/or R-free to score. If it is a predicted structure, it should use the structure's predicted metrics, like pLDDT.

Assume that ODesign model is installed (just put a placeholder for now). Replace assemble_screening_library and dock_library with ODesign model 
call. Instead of dock_library,it should dock every N generations, say 10. It should combine the predicted mdoel score (if the model provides a score on binding affinity or complementarity) with the docking model score. Start with results of chemical structures from literature_agent as a starting point or use the similarity of the generated output with the similar
ligands as guidance for the model. Additionally use the similarity of the generated output with the similar ligands to add to the score.

