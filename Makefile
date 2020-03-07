all:
	# Preamble
	echo "EESchema-LIBRARY Version 2.4" > FPGA_Lattice_ECP5.lib
	echo "#encoding utf-8" >> FPGA_Lattice_ECP5.lib
	# U series
	./lattice_to_kicad.py ECP5-U-12 csv_data/ecp5u/ecp5u12pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-U-25 csv_data/ecp5u/ecp5u25pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-U-45 csv_data/ecp5u/ecp5u45pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-U-85 csv_data/ecp5u/ecp5u85pinout.csv >> FPGA_Lattice_ECP5.lib
	# UM series
	./lattice_to_kicad.py ECP5-UM-25 csv_data/ecp5um/ecp5um25pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-UM-45 csv_data/ecp5um/ecp5um45pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-UM-85 csv_data/ecp5um/ecp5um85pinout.csv >> FPGA_Lattice_ECP5.lib
	# UM-5G series (5G SERDES)
	./lattice_to_kicad.py ECP5-UM5G-25 csv_data/ecp5um_5g/ecp5um5g-25pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-UM5G-45 csv_data/ecp5um_5g/ecp5um5g-45pinout.csv >> FPGA_Lattice_ECP5.lib
	./lattice_to_kicad.py ECP5-UM5G-85 csv_data/ecp5um_5g/ecp5um5g-85pinout.csv >> FPGA_Lattice_ECP5.lib
	# Postamble
	echo "#End Library" >> FPGA_Lattice_ECP5.lib
