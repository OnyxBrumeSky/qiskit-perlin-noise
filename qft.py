from qiskit import QuantumCircuit


from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import QFTGate


def apply_qft_interpolation(
    qc: QuantumCircuit,
    n_dim: int,
    n_ancilla: int,
    measure: bool = True
) -> QuantumCircuit:
    """
    Découpe le circuit en n_dim morceaux de taille égale,
    ajoute n_ancilla qubits ancilla par morceau,
    applique :
      1. QFT locale sur le morceau
      2. QFT globale sur (morceau + ancilla)
      3. mesure optionnelle

    Paramètres
    ----------
    qc : QuantumCircuit
        Circuit existant contenant les qubits de données.
    n_dim : int
        Nombre de morceaux.
    n_ancilla : int
        Nombre d’ancilla à ajouter par morceau.
    measure : bool
        Si True, mesure tous les qubits.

    Retour
    ------
    QuantumCircuit
        Nouveau circuit avec interpolation QFT.
    """

    total_data = qc.num_qubits

    if total_data % n_dim != 0:
        raise ValueError(
            f"Le nombre de qubits ({total_data}) doit être divisible par n_dim ({n_dim})."
        )

    chunk_size = total_data // n_dim

    # Nouveau registre ancilla
    anc_regs = [
        QuantumRegister(n_ancilla, name=f"anc{i}")
        for i in range(n_dim)
    ]

    # Nouveau circuit avec anciens qubits + ancilla
    new_qc = QuantumCircuit(*qc.qregs)

    for anc in anc_regs:
        new_qc.add_register(anc)

    # recopier le circuit original
    new_qc.compose(qc, inplace=True)

    # mesure optionnelle
    if measure:
        creg = ClassicalRegister(new_qc.num_qubits, name="c")
        new_qc.add_register(creg)
    
    # interpolation QFT par bloc
    for i in range(n_dim):
        start = i * chunk_size
        end = (i + 1) * chunk_size

        # bloc courant
        data_block = new_qc.qubits[start:end]
        anc_block = list(anc_regs[i])

        # 1. QFT locale sur les qubits du bloc
        qft_local = QFTGate(chunk_size)
        new_qc.append(qft_local, data_block)

        # 2. mélange simple avec ancilla (copie de structure fréquentielle)
        for j in range(min(chunk_size, n_ancilla)):
            new_qc.swap(data_block[j], anc_block[j])

        #print("\n\n\n\n\nwtf")
        control = data_block[-1]
        for target in data_block[:-1]:
            new_qc.cx(control, target)
        
        # 3. QFT globale sur bloc + ancilla
        full_block = data_block + anc_block
        #full_block = full_block[::-1]  # optionnel : ordre little-endian propre

        qft_interp = QFTGate(len(full_block))
        new_qc.append(qft_interp, full_block)

        # mesure optionnelle
        if measure:
            #full_block = full_block[::-1]
            new_qc.measure(full_block)

    return new_qc