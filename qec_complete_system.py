from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.providers.aer import AerSimulator
from qiskit.visualization import plot_histogram
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple

class QuantumErrorCorrectionCode:
    """Clase base para códigos de corrección cuántica de errores"""
    
    def __init__(self, name: str, n_data_qubits: int, n_logical_qubits: int):
        self.name = name
        self.n_data = n_data_qubits
        self.n_logical = n_logical_qubits
        
    def encode_state(self, circuit: QuantumCircuit, logical_qubits: List[int], data_qubits: List[int]):
        """Codifica el estado lógico en qubits de datos"""
        raise NotImplementedError
        
    def get_stabilizers(self) -> List[str]:
        """Retorna los estabilizadores del código"""
        raise NotImplementedError
        
    def decode_syndrome(self, syndrome: str) -> int:
        """Decodifica el síndrome para determinar qué qubit corregir"""
        raise NotImplementedError

class ThreeQubitCode(QuantumErrorCorrectionCode):
    """Código de 3 qubits para corrección de bit-flip"""
    
    def __init__(self):
        super().__init__("3-Qubit Code", 3, 1)
        
    def encode_state(self, circuit: QuantumCircuit, logical_qubits: List[int], data_qubits: List[int]):
        """Codifica |0⟩ -> |000⟩, |1⟩ -> |111⟩, |+⟩ -> (|000⟩+|111⟩)/√2"""
        if len(logical_qubits) != 1 or len(data_qubits) != 3:
            raise ValueError("3-Qubit code requires 1 logical and 3 data qubits")
            
        # CNOT en cascada para crear la codificación
        circuit.cx(logical_qubits[0], data_qubits[0])
        circuit.cx(data_qubits[0], data_qubits[1])
        circuit.cx(data_qubits[0], data_qubits[2])
        
    def get_stabilizers(self) -> List[str]:
        """Estabilizadores Z₀Z₁ y Z₁Z₂"""
        return ['ZZI', 'IZZ']
        
    def decode_syndrome(self, syndrome: str) -> int:
        """
        Decodifica el síndrome de 2 bits:
        00 -> Sin error
        01 -> Error en qubit 0
        11 -> Error en qubit 1  
        10 -> Error en qubit 2
        """
        syndrome_map = {
            '00': -1,  # Sin error
            '01': 0,   # Error en qubit 0
            '11': 1,   # Error en qubit 1
            '10': 2    # Error en qubit 2
        }
        return syndrome_map.get(syndrome, -1)

class QECSimulator:
    """Simulador para experimentos de corrección cuántica de errores"""
    
    def __init__(self, code: QuantumErrorCorrectionCode):
        self.code = code
        self.simulator = AerSimulator()
        
    def create_encoding_circuit(self, initial_state: str = 'plus') -> QuantumCircuit:
        """Crea el circuito de codificación"""
        q_logical = QuantumRegister(1, 'logical')
        q_data = QuantumRegister(self.code.n_data, 'data')
        
        circuit = QuantumCircuit(q_logical, q_data)
        
        # Preparar estado inicial
        if initial_state == 'plus':
            circuit.h(q_logical[0])  # |+⟩ = (|0⟩+|1⟩)/√2
        elif initial_state == 'one':
            circuit.x(q_logical[0])  # |1⟩
        # Para '0' no hacemos nada (estado por defecto)
        
        # Codificar
        self.code.encode_state(circuit, [0], list(range(self.code.n_data)))
        
        return circuit
        
    def create_syndrome_measurement_circuit(self, data_qubits: List[int]) -> QuantumCircuit:
        """Crea el circuito para medir síndromes"""
        n_stabilizers = len(self.code.get_stabilizers())
        q_data = QuantumRegister(len(data_qubits), 'data')
        q_ancilla = QuantumRegister(n_stabilizers, 'ancilla')
        c_syndrome = ClassicalRegister(n_stabilizers, 'syndrome')
        
        circuit = QuantumCircuit(q_data, q_ancilla, c_syndrome)
        
        # Para el código de 3 qubits: medir Z₀Z₁ y Z₁Z₂
        # Estabilizador 1: Z₀Z₁
        circuit.cx(q_data[0], q_ancilla[0])
        circuit.cx(q_data[1], q_ancilla[0])
        
        # Estabilizador 2: Z₁Z₂  
        circuit.cx(q_data[1], q_ancilla[1])
        circuit.cx(q_data[2], q_ancilla[1])
        
        # Medir ancillas
        circuit.measure(q_ancilla, c_syndrome)
        
        return circuit
        
    def create_full_qec_circuit(self, initial_state: str = 'plus', 
                               error_prob: float = 0.0, 
                               error_qubit: int = None) -> QuantumCircuit:
        """Crea el circuito completo de QEC con corrección dinámica"""
        # Registros cuánticos y clásicos
        q_logical = QuantumRegister(1, 'logical')
        q_data = QuantumRegister(self.code.n_data, 'data')
        q_ancilla = QuantumRegister(2, 'ancilla')
        c_syndrome = ClassicalRegister(2, 'syndrome')
        c_final = ClassicalRegister(self.code.n_data, 'final')
        
        circuit = QuantumCircuit(q_logical, q_data, q_ancilla, c_syndrome, c_final)
        
        # 1. Codificación
        if initial_state == 'plus':
            circuit.h(q_logical[0])
        elif initial_state == 'one':
            circuit.x(q_logical[0])
            
        self.code.encode_state(circuit, [0], [0, 1, 2])
        circuit.barrier()
        
        # 2. Simular error (opcional)
        if error_qubit is not None and 0 <= error_qubit < self.code.n_data:
            circuit.x(q_data[error_qubit])  # Bit flip error
            circuit.barrier()
            
        # 3. Medición de síndrome
        circuit.cx(q_data[0], q_ancilla[0])
        circuit.cx(q_data[1], q_ancilla[0])
        circuit.cx(q_data[1], q_ancilla[1])
        circuit.cx(q_data[2], q_ancilla[1])
        circuit.measure(q_ancilla, c_syndrome)
        circuit.barrier()
        
        # 4. Corrección condicional (control dinámico)
        with circuit.if_test((c_syndrome, 1)):  # síndrome = '01'
            circuit.x(q_data[0])
        with circuit.if_test((c_syndrome, 3)):  # síndrome = '11' 
            circuit.x(q_data[1])
        with circuit.if_test((c_syndrome, 2)):  # síndrome = '10'
            circuit.x(q_data[2])
            
        # 5. Medición final para verificación
        circuit.measure(q_data, c_final)
        
        return circuit
        
    def run_experiment(self, circuit: QuantumCircuit, shots: int = 1024) -> Dict:
        """Ejecuta el experimento y retorna los resultados"""
        transpiled_circuit = transpile(circuit, self.simulator)
        job = self.simulator.run(transpiled_circuit, shots=shots)
        result = job.result()
        counts = result.get_counts()
        return counts
        
    def calculate_logical_error_rate(self, results: Dict, expected_logical_state: str) -> float:
        """Calcula la tasa de error lógico"""
        total_shots = sum(results.values())
        error_shots = 0
        
        for outcome, count in results.items():
            # Extraer los bits de datos finales (últimos 3 bits)
            data_bits = outcome.split()[-1]  # Formato: "syndrome_bits data_bits"
            
            # Determinar el estado lógico medido
            if data_bits in ['000', '001', '010', '100']:
                measured_logical = '0'
            elif data_bits in ['111', '110', '101', '011']:
                measured_logical = '1'
            else:
                # Estado mixto - contar como error
                error_shots += count
                continue
                
            if measured_logical != expected_logical_state:
                error_shots += count
                
        return error_shots / total_shots if total_shots > 0 else 0
        
    def benchmark_performance(self, shots: int = 1000) -> Dict:
        """Benchmark del rendimiento del código QEC"""
        results = {}
        
        # Test sin errores
        circuit_no_error = self.create_full_qec_circuit('plus', error_qubit=None)
        counts_no_error = self.run_experiment(circuit_no_error, shots)
        results['no_error'] = {
            'counts': counts_no_error,
            'error_rate': self.calculate_logical_error_rate(counts_no_error, '0')
        }
        
        # Test con errores en cada qubit
        for i in range(3):
            circuit_error = self.create_full_qec_circuit('plus', error_qubit=i)
            counts_error = self.run_experiment(circuit_error, shots)
            results[f'error_qubit_{i}'] = {
                'counts': counts_error,
                'error_rate': self.calculate_logical_error_rate(counts_error, '0')
            }
            
        return results

def main():
    """Función principal para demostrar el sistema QEC"""
    print("=== Sistema de Corrección Cuántica de Errores ===\n")
    
    # Inicializar el código y simulador
    code = ThreeQubitCode()
    simulator = QECSimulator(code)
    
    print(f"Código: {code.name}")
    print(f"Qubits de datos: {code.n_data}")
    print(f"Qubits lógicos: {code.n_logical}")
    print(f"Estabilizadores: {code.get_stabilizers()}\n")
    
    # Ejecutar benchmark
    print("Ejecutando benchmark de rendimiento...")
    results = simulator.benchmark_performance(shots=1000)
    
    # Mostrar resultados
    print("\n=== Resultados del Benchmark ===")
    for scenario, data in results.items():
        print(f"\nEscenario: {scenario}")
        print(f"Tasa de error lógico: {data['error_rate']:.3f}")
        print(f"Distribución de resultados: {dict(list(data['counts'].items())[:3])}...")
        
    # Crear y mostrar circuito de ejemplo
    print("\n=== Circuito de Ejemplo ===")
    example_circuit = simulator.create_full_qec_circuit('plus', error_qubit=1)
    print(f"Profundidad del circuito: {example_circuit.depth()}")
    print(f"Número de puertas: {example_circuit.size()}")
    print(f"Qubits utilizados: {example_circuit.num_qubits}")
    
    # Análisis teórico vs práctico
    print("\n=== Análisis de Rendimiento ===")
    no_error_rate = results['no_error']['error_rate']
    avg_error_rate = np.mean([results[f'error_qubit_{i}']['error_rate'] for i in range(3)])
    
    print(f"Tasa de error sin errores introducidos: {no_error_rate:.3f}")
    print(f"Tasa de error promedio con corrección: {avg_error_rate:.3f}")
    print(f"Mejora de la corrección: {(1 - avg_error_rate/max(no_error_rate, 0.001)):.1%}")

if __name__ == "__main__":
    main()
