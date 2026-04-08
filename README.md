# Perlin Noise using Quantun
I am trying to produce a perlin noise and produce it to N dimmensions using quantum programming. 
My steps are : generate random amplitude for states. Then load it to quantum states using Grover Rodolph algo. Then aply qft interpolation to smooth the result.
Here are my outputs for now :
![alt text](<Screenshot from 2026-04-08 19-17-13.png>)
![alt text](<Screenshot from 2026-04-08 19-16-58.png>)

# Evolution of projet
For now my first step seems to be working with random generation using a seed. The loading part is not working for some reason. The output for a 2D shows that something is wrong. It could be for the way I load data or maybe the way I measure (wrong order for exemple). Still seeking a way to make it work.
Here is the output circuit: 
![alt text](<Screenshot from 2026-04-08 19-21-57.png>)



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