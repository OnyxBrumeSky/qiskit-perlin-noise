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
        resolution: int = 3,
        n_dimmensions: int = 1,
        seed: int | str | None = None,
        distrib: str = "random",
        shots: int = 50_000,
        # ── paramètres temporels ──────────────────────────────────────────
        n_frames: int = 1,               # nombre de frames à générer
        interp: str = "cosine",          # "cosine" | "linear"
        seed_b: int | str | None = None, # graine pour la distribution cible
    ):
        self.resolution = resolution
        self.n_dims = n_dimmensions
        self.shots = shots
        self.n_frames = n_frames
        self.interp = interp

        n_states = (2 ** resolution) ** n_dimmensions
        self.ancilla = resolution - 1
        self.chunk_size = resolution + self.ancilla

        # Distribution source (t=0) et cible (t=1)
        self.distrib_a = DistributionGenerator(
            n_states=n_states, seed=seed, dist_type=distrib
        )
        self.distrib_b = DistributionGenerator(
            n_states=n_states,
            seed=seed_b if seed_b is not None else (seed + 1 if isinstance(seed, int) else None),
            dist_type=distrib,
        )

        self.n_qubits = (resolution + self.ancilla) * n_dimmensions

    # ── interpolation ─────────────────────────────────────────────────────

    def _interp_factor(self, t: float) -> float:
        """Retourne le facteur d'interpolation lissé pour t ∈ [0, 1]."""
        if self.interp == "cosine":
            return (1 - np.cos(np.pi * t)) / 2
        return t  # linéaire

    def _interpolated_amplitudes(self, t: float) -> np.ndarray:
        """Amplitudes √(probas interpolées) pour l'instant t."""
        alpha = self._interp_factor(t)
        probs = (1 - alpha) * self.distrib_a.probabilities + alpha * self.distrib_b.probabilities
        probs = np.clip(probs, 0, None)
        probs /= probs.sum()          # renormalisation numérique
        return np.sqrt(probs)

    # ── construction du circuit pour un instant t ─────────────────────────

    def _build_circuit(self, amplitudes: np.ndarray) -> QuantumCircuit:
        """Reconstruit le circuit complet avec les amplitudes données."""
        n_dimmensions = self.n_dims
        resolution = self.resolution
        ancilla = self.ancilla
        chunk_size = self.chunk_size
        n_qubits = self.n_qubits

        qc = QuantumCircuit(n_qubits, n_qubits)
        start = ancilla * n_dimmensions

        prep_gate = StatePreparation(amplitudes)
        qc.append(prep_gate, list(np.arange(start, n_qubits)))

        qft_a = QFTGate(resolution)
        qft_b = QFTGate(chunk_size)

        for i in range(n_dimmensions):
            start_a = start + i * resolution
            end_a = start_a + resolution
            ancilla_tbl = np.arange(i * ancilla, i * ancilla + ancilla)
            chunk = np.arange(start_a, end_a)
            tbl = list(ancilla_tbl)
            tbl.extend(chunk)

            qc.append(qft_a, tbl[-resolution:])
            for j in range(ancilla):
                qc.swap(tbl[j], tbl[ancilla + j])
            for j in range(resolution - 1):
                qc.cx(tbl[-1], tbl[ancilla + j])
            qc.append(qft_b, tbl)
            qc.measure(tbl, list(np.arange(i * chunk_size, i * chunk_size + chunk_size)))

        return qc

    # ── compatibilité avec l'API d'origine ────────────────────────────────

    def get_circuit(self) -> QuantumCircuit:
        """Retourne le circuit à t=0."""
        return self._build_circuit(self._interpolated_amplitudes(0.0))

    # ── simulation (une frame ou toutes les frames) ───────────────────────

    def _simulate_circuit(self, qc: QuantumCircuit) -> dict:
        """Simule un circuit et retourne les counts normalisés."""
        sim = AerSimulator()
        job = sim.run(transpile(qc, sim), shots=self.shots)
        counts = job.result().get_counts()
        return {k: v / self.shots for k, v in sorted(counts.items())}

    def _counts_to_data(self, counts: dict):
        """Convertit les counts en données selon la dimension."""
        size = 2 ** self.chunk_size
        chunk_size = self.chunk_size

        if self.n_dims == 1:
            return counts

        elif self.n_dims == 2:
            table = np.zeros((size, size))
            for bitstring, count in counts.items():
                x = int(bitstring[:chunk_size], 2)
                y = int(bitstring[-chunk_size:], 2)
                table[x][y] = count * self.shots   # dénormalise pour remplir la table
            return (table - table.min()) / (table.max() - table.min() + 1e-9)

        elif self.n_dims == 3:
            vol = np.zeros((size, size, size))
            for bitstring, count in counts.items():
                x = int(bitstring[:chunk_size], 2) % size
                y = int(bitstring[chunk_size:2 * chunk_size], 2) % size
                z = int(bitstring[-chunk_size:], 2) % size
                vol[x, y, z] = count * self.shots
            return (vol - vol.min()) / (vol.max() - vol.min() + 1e-9)

    def simulate(self, shots: int | None = None) -> dict:
        """
        Simule une ou plusieurs frames selon n_frames.

        Si n_frames == 1  → comportement identique à l'original.
        Si n_frames  > 1  → self.frames est une liste de données par frame,
                            self.data correspond à la dernière frame.
        """
        if shots is not None:
            self.shots = shots

        if self.n_frames == 1:
            amplitudes = self._interpolated_amplitudes(0.0)
            qc = self._build_circuit(amplitudes)
            self.counts = self._simulate_circuit(qc)
            self.data = self._counts_to_data(self.counts)
            self.frames = [self.data]
            return self.counts

        # ── animation : n_frames > 1 ──────────────────────────────────────
        self.frames = []
        ts = np.linspace(0, 1, self.n_frames)

        for i, t in enumerate(ts):
            print(f"  frame {i + 1}/{self.n_frames}  (t={t:.3f})")
            amplitudes = self._interpolated_amplitudes(t)
            qc = self._build_circuit(amplitudes)
            counts = self._simulate_circuit(qc)
            self.frames.append(self._counts_to_data(counts))

        self.data = self.frames[-1]
        self.counts = {}   # non pertinent en mode multi-frames
        return self.counts

    # ── visualisation ─────────────────────────────────────────────────────

    def _plot_1D(self):
        self.distrib_a.plot()
        if self.n_frames == 1:
            plot_histogram(self.data)
        else:
            fig, axes = plt.subplots(1, self.n_frames, figsize=(4 * self.n_frames, 3))
            for i, frame in enumerate(self.frames):
                ax = axes[i] if self.n_frames > 1 else axes
                ax.bar(list(frame.keys()), list(frame.values()))
                ax.set_title(f"t={i/(self.n_frames-1):.2f}" if self.n_frames > 1 else "t=0")
                ax.tick_params(axis="x", labelrotation=90, labelsize=6)
            plt.tight_layout()
            plt.show()

    def _plot_2D(self, frame_data=None):
        data = frame_data if frame_data is not None else self.data
        q = np.quantile(data, [0.35, 0.40, 0.60, 0.70, 0.89, 0.95, 0.99])
        biome = np.digitize(data, q)
        biome_colors = [
            "#2b4c7e", "#4f8fbf", "#e6d3a3", "#a7d08c",
            "#4f8b4a", "#7c9a6d", "#8a8a8a", "#f2f2e6",
        ]
        biome_labels = ["Eau profonde", "Eau", "Plage", "Prairie",
                        "Forêt", "Collines", "Montagnes", "Neige"]
        cmap = ListedColormap(biome_colors)
        fig, axes = plt.subplots(1, 2, figsize=(16, 5))
        axes[0].imshow(data, cmap="gray")
        axes[0].set_title("Brut")
        axes[0].axis("off")
        im = axes[1].imshow(biome, cmap=cmap, vmin=0, vmax=7)
        axes[1].set_title("Biomes")
        axes[1].axis("off")
        patches = [plt.Rectangle((0, 0), 1, 1, color=biome_colors[i]) for i in range(8)]
        axes[1].legend(patches, biome_labels, loc="lower right", fontsize=8)
        plt.tight_layout()
        plt.show()

    def _plot_3D(self, frame_data=None):
        data = frame_data if frame_data is not None else self.data
        n_lambda = data.shape[2]
        lambdas = np.linspace(400, 700, n_lambda)

        def gaussian(l, peak, width):
            return np.exp(-0.5 * ((l - peak) / width) ** 2)

        red = gaussian(lambdas, 610, 40);   red   /= red.max()
        green = gaussian(lambdas, 540, 40); green /= green.max()
        blue = gaussian(lambdas, 450, 30);  blue  /= blue.max()

        h, w, _ = data.shape
        img = np.zeros((h, w, 3))
        for i in range(h):
            for j in range(w):
                s = data[i, j, :]
                img[i, j] = [np.sum(s * red), np.sum(s * green), np.sum(s * blue)]
        img = (img - img.min()) / (img.max() - img.min() + 1e-9)
        plt.figure(figsize=(6, 6))
        plt.imshow(img, origin="lower")
        plt.title("3D spectral projection (x,y,λ → RGB)")
        plt.axis("off")
        plt.show()

    def _data_to_biomes(self, data):
        q = np.quantile(data, [0.35, 0.40, 0.60, 0.70, 0.89, 0.95, 0.99])
        biome = np.digitize(data, q)
    
        biome_colors = [
            "#2b4c7e", "#4f8fbf", "#e6d3a3", "#a7d08c",
            "#4f8b4a", "#7c9a6d", "#8a8a8a", "#f2f2e6",
        ]
    
        cmap = ListedColormap(biome_colors)
        return biome, cmap
    
    def animate(self, interval: int = 200, save_path: str | None = None):
        """
        Affiche (ou sauvegarde) une animation matplotlib des frames générées.
        Nécessite n_frames > 1 et simulate() appelé au préalable.

        interval   : délai entre frames en ms (défaut 200 ms → 5 fps)
        save_path  : chemin .gif ou .mp4 pour sauvegarder (None = affichage seul)
        """
        import matplotlib.animation as animation

        if not hasattr(self, "frames") or len(self.frames) <= 1:
            raise RuntimeError("Appelez simulate() avec n_frames > 1 avant animate().")

        if self.n_dims == 1:
            fig, ax = plt.subplots(figsize=(8, 4))
            keys = list(self.frames[0].keys())
            bar_container = ax.bar(keys, list(self.frames[0].values()))
            ax.set_ylim(0, max(max(f.values()) for f in self.frames) * 1.1)
            title = ax.set_title("t = 0.00")

            def update(i):
                vals = list(self.frames[i].values())
                for bar, h in zip(bar_container, vals):
                    bar.set_height(h)
                t = i / (self.n_frames - 1) if self.n_frames > 1 else 0
                title.set_text(f"t = {t:.2f}")
                return list(bar_container) + [title]

        elif self.n_dims == 2:
            fig, ax = plt.subplots(figsize=(6, 6))
        
            biome0, cmap = self._data_to_biomes(self.frames[0])
        
            im = ax.imshow(biome0, cmap=cmap, vmin=0, vmax=7, animated=True)
            ax.axis("off")
            title = ax.set_title("t = 0.00")
        
            def update(i):
                biome, _ = self._data_to_biomes(self.frames[i])
                im.set_data(biome)
        
                t = i / (self.n_frames - 1) if self.n_frames > 1 else 0
                title.set_text(f"t = {t:.2f}")
                return [im, title]
        elif self.n_dims == 3:
            # projection spectrale pour chaque frame
            projections = []
            for frame in self.frames:
                n_lambda = frame.shape[2]
                lambdas = np.linspace(400, 700, n_lambda)

                def gaussian(l, peak, width):
                    return np.exp(-0.5 * ((l - peak) / width) ** 2)

                red = gaussian(lambdas, 610, 40);   red   /= red.max()
                green = gaussian(lambdas, 540, 40); green /= green.max()
                blue = gaussian(lambdas, 450, 30);  blue  /= blue.max()

                h, w, _ = frame.shape
                img = np.zeros((h, w, 3))
                for ii in range(h):
                    for jj in range(w):
                        s = frame[ii, jj, :]
                        img[ii, jj] = [np.sum(s * red), np.sum(s * green), np.sum(s * blue)]
                img = (img - img.min()) / (img.max() - img.min() + 1e-9)
                projections.append(img)

            fig, ax = plt.subplots(figsize=(6, 6))
            im = ax.imshow(projections[0], origin="lower", animated=True)
            ax.axis("off")
            title = ax.set_title("t = 0.00")

            def update(i):
                im.set_data(projections[i])
                t = i / (self.n_frames - 1) if self.n_frames > 1 else 0
                title.set_text(f"t = {t:.2f}")
                return [im, title]

        ani = animation.FuncAnimation(
            fig, update, frames=self.n_frames, interval=interval, blit=True
        )

        if save_path:
            writer = "pillow" if save_path.endswith(".gif") else "ffmpeg"
            ani.save(save_path, writer=writer, fps=1000 // interval)
            print(f"Animation sauvegardée : {save_path}")
        else:
            plt.show()

        return ani

    def plot(self, e: int = 0):
        if self.n_dims == 1:
            self._plot_1D()
        elif self.n_dims == 2:
            self._plot_2D()
        elif self.n_dims == 3:
            self._plot_3D()


# ── Exemples ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── 1D animation ─────────────────────────────────────────────────────
    gen1d = PerlinGenerator(
        n_dimmensions=1, resolution=3,
        distrib="random", seed=42,
        n_frames=60, interp="cosine",
    )
    gen1d.simulate()
    gen1d.animate(interval=200, save_path="perlin_1d.gif")

    # ── 2D animation (carte + biomes) ────────────────────────────────────
    gen2d = PerlinGenerator(
        n_dimmensions=2, resolution=3,
        distrib="random", seed=0,
        n_frames=60, interp="cosine",
    )
    gen2d.simulate()
    gen2d.animate(interval=200, save_path="perlin_2d.gif")

    # ── 3D animation spectrale ───────────────────────────────────────────
    gen3d = PerlinGenerator(
        n_dimmensions=3, resolution=3,
        distrib="random", seed=7,
        n_frames=60, interp="cosine",
    )
    qc = gen3d.get_circuit()
    print(qc)
    
    gen3d.simulate()
    gen3d.animate(interval=200, save_path="perlin_3d.gif")
