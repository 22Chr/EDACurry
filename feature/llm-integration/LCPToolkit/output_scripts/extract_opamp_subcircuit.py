
import argparse
from edacurry import parse_xml

def main():
    parser = argparse.ArgumentParser(description='Parse an XML circuit and extract the OPAMP subcircuit.')
    parser.add_argument('-i', '--input', required=True, help='Path to the input XML file')
    args = parser.parse_args()

    # Parse the XML file
    circuit = parse_xml(args.input)

    # Find the OPAMP subcircuit
    opamp_subckt = edacurry.find_subckt(circuit, "OPAMP1")

    if opamp_subckt:
        print("OPAMP Subcircuit found:")
        print(f"Name: {opamp_subckt.name}")
        print("Nodes:", [node.name for node in opamp_subckt.nodes])
        # You can further process or export the subcircuit as needed
    else:
        print("OPAMP Subcircuit not found.")

if __name__ == "__main__":
    main()
```

