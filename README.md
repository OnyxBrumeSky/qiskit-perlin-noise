# Perlin Noise using Quantun
I am trying to produce a perlin noise and produce it to N dimmensions using quantum programming. 
My steps are : generate random amplitude for states. Then load it to quantum states using Grover Rodolph algo. Then aply qft interpolation to smooth the result.
Here are my latest outputs :
![alt text](image.png)

# Evolution of projet
Success. After using the StepPreparation from qiskit and creating a static circuit, the perlin noise seems to be working as expected. 

The circuit now looks like this : 
![alt text](image-1.png)
Notice that all the measurements are not shown as it didn't fit on my screen.

The file containing the work is perlinv2.py.
My next step is to clean everything and make it as a reusable python library and maybe a rust library too.



Sources : 
1) https://qetel.usal.es/blog/quantum-perlin-noise#_ednref1
2) https://qetel.usal.es/blog/quantum-perlin-noise-ii-generating-worlds
3) https://arxiv.org/pdf/2310.19309
4) https://arxiv.org/pdf/quant-ph/0208112
5) https://arxiv.org/pdf/2203.06196
6) https://medium.com/qiskit/introducing-procedural-generation-using-quantum-computation-956e67603d95
7) https://medium.com/qiskit/introducing-a-quantum-procedure-for-map-generation-eb6663a3f13d
8) https://arxiv.org/pdf/2203.06196

The code has been generated with claude and supervised by me