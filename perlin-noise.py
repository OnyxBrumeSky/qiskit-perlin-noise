from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import QFTGate
from qiskit_aer import AerSimulator
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from qiskit.circuit.library import StatePreparation
from distribution_generator import DistributionGenerator
from qiskit.visualization import plot_histogram


class PerlinGenerator:

    def __init__(
        self,
        resolution : int = 3, 
        n_dimmensions : int = 1,
        seed : int | str | None = None, 
        distrib : str = "random", 
        shots : int = 50_000,
):
        ancilla = resolution - 1
        n_states = (2**resolution)**n_dimmensions
        self.distrib = DistributionGenerator(n_states=n_states, seed=seed, dist_type = distrib)

        amplitudes = np.sqrt(self.distrib.probabilities)
        self.chunk_size = resolution + ancilla
        
        self.n_qubits = (resolution + ancilla) * n_dimmensions
        self.resolution = resolution
        self.qc = QuantumCircuit(self.n_qubits, self.n_qubits)
        self.n_dims = n_dimmensions
        self.shots = shots
        start = ancilla * n_dimmensions

        self.prepGate = StatePreparation(amplitudes)
        self.qc.append(
            self.prepGate, 
            list(np.arange(
                start, 
                self.n_qubits)))
        qft_a = QFTGate(resolution)
        qft_b = QFTGate(self.chunk_size)

        for i in range(n_dimmensions):
            
            start_a = start + i * resolution
            end_a = start_a + resolution
            ancilla_tbl = np.arange(i * ancilla, i * ancilla + ancilla)
            chunk = np.arange(start_a, end_a )
            tbl = list(ancilla_tbl)
            tbl.extend(chunk)
            self.qc.append(qft_a, tbl[-resolution:])

            for j in range(ancilla):
                self.qc.swap(tbl[j], tbl[ancilla + j])
            for j in range(resolution - 1):
                self.qc.cx(tbl[-1], tbl[ancilla + j])

            self.qc.append(qft_b, tbl)

            self.qc.measure(tbl, list(np.arange(i * self.chunk_size, i * self.chunk_size + self.chunk_size)))

    def get_circuit(self) -> QuantumCircuit: 
        return self.qc

    def simulate(self, shots: int = 50_000) -> dict:
        sim = AerSimulator()
        job = sim.run(transpile(self.qc, sim), shots=shots)
        counts = job.result().get_counts()
        self.counts = {k: v / shots for k, v in sorted(counts.items())}
        size = 2**(self.chunk_size)

        if self.n_dims == 1 : # Simple distribution
            self.data = self.counts
            
        elif self.n_dims == 2 : # 2D map
            table = np.zeros((size,size))
            for bitstring, count in counts.items():
                x = int(bitstring[:self.chunk_size],2)
                y = int(bitstring[-self.chunk_size:],2)
                table[x][y] = count
            self.data = (table - table.min()) / (table.max() - table.min())
        elif self.n_dims == 3:
            vol = np.zeros((size, size, size))
        
            for bitstring, count in counts.items():
                x = int(bitstring[:self.chunk_size], 2) % size
                y = int(bitstring[self.chunk_size:2*self.chunk_size], 2) % size
                z = int(bitstring[-self.chunk_size:], 2) % size
                vol[x, y, z] = count
        
            self.data = (vol - vol.min()) / (vol.max() - vol.min() + 1e-9)
            
        return self.counts

    def _plot_1D(self):
        self.distrib.plot()
        plot_histogram(self.data)

    def _plot_2D(self):
        data = self.data
        q = np.quantile(data, [0.35, 0.40, 0.60, 0.70, 0.89, 0.95, 0.99])
        biome = np.digitize(data, q)

        biome_colors = [
            "#2b4c7e",  # eau profonde
            "#4f8fbf",  # eau
            "#e6d3a3",  # plage
            "#a7d08c",  # prairie
            "#4f8b4a",  # forêt
            "#7c9a6d",  # collines
            "#8a8a8a",  # montagnes
            "#f2f2e6"   # neige
        ]
    
        biome_labels = [
            "Eau profonde",
            "Eau",
            "Plage",
            "Prairie",
            "Forêt",
            "Collines",
            "Montagnes",
            "Neige"
        ]
    
        cmap = ListedColormap(biome_colors)
    
        fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    
        axes[0].imshow(data, cmap='gray')
        axes[0].set_title("Brut")
        axes[0].axis('off')
    
    
    
        im = axes[1].imshow(biome, cmap=cmap, vmin=0, vmax=7)
        axes[1].set_title("Biomes")
        axes[1].axis('off')
    
        patches = [plt.Rectangle((0, 0), 1, 1, color=biome_colors[i]) for i in range(8)]
        axes[1].legend(patches, biome_labels, loc='lower right', fontsize=8)
    
        plt.tight_layout()
        plt.show()

    def _plot_3D(self):    
        data = self.data  # (x, y, λ)
    
        n_lambda = data.shape[2]
        lambdas = np.linspace(400, 700, n_lambda)
    
        # --- sensibilités spectrales ---
        def gaussian(l, peak, width):
            return np.exp(-0.5 * ((l - peak) / width) ** 2)
    
        red   = gaussian(lambdas, 610, 40)
        green = gaussian(lambdas, 540, 40)
        blue  = gaussian(lambdas, 450, 30)
    
        red /= red.max()
        green /= green.max()
        blue /= blue.max()
    
        # --- conversion spectre -> RGB ---
        h, w, _ = data.shape
        img = np.zeros((h, w, 3))
    
        for i in range(h):
            for j in range(w):
                spectrum = data[i, j, :]
    
                r = np.sum(spectrum * red)
                g = np.sum(spectrum * green)
                b = np.sum(spectrum * blue)
    
                img[i, j] = [r, g, b]

        # normalisation
        img = (img - img.min()) / (img.max() - img.min() + 1e-9)
    
        plt.figure(figsize=(6, 6))
        plt.imshow(img, origin="lower")
        plt.title("3D spectral projection (x,y,λ → RGB)")
        plt.axis("off")
        plt.show()
    
    def plot(self, e : int = 0):
        if self.n_dims == 1 :
            self._plot_1D()
        elif self.n_dims == 2 :
           self. _plot_2D()
        elif self.n_dims == 3:
            self._plot_3D()


# Exemple
if __name__ == "__main__":
    test = PerlinGenerator(n_dimmensions=3, resolution=3, distrib="random")
    qc = test.get_circuit()
    display(qc.draw(output="mpl"))
    test.simulate()
    test.plot()
