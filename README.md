# Perlin Noise using Quantun
I am trying to produce a perlin noise and produce it to N dimmensions using quantum programming. 
My steps are : generate random amplitude for states. Then load it to quantum states using Grover Rodolph algo. Then aply qft interpolation to smooth the result.
Here are my latest outputs :
![alt text](<Screenshot from 2026-04-09 18-15-05.png>)

# Evolution of projet
I am now using the Prep state of qiskit to load data. It is working as expected as shown in figures
![alt text](<Screenshot from 2026-04-09 18-14-04.png>)

But i still have an issue on how to correctly handle the measurment. You can see it on the circuit where some of the qft are mixed up. This affects the map generation as you can see. 
![alt text](<Screenshot from 2026-04-09 18-14-26.png>)
Now the files I used claude to create a distribution function. The work is now in the loading.py file. It is a bit messy and will be cleanned when I reach a good output



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