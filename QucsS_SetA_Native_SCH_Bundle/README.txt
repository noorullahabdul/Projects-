Qucs-S native schematic bundle — Set A low-pass filter

Files
- SetA_Base_30dB.sch: 6-stage passive RC ladder
- SetA_G2_45dB.sch: 8-stage passive RC ladder

Open each .sch in Qucs-S, select Ngspice, and run AC analysis (F2). Both use a 1 kOhm source resistance, 100 kOhm load, and 10 kOhm series resistors. The base case uses 6.8 nF shunt capacitors; the higher-attenuation case uses 6.85 nF. Calculated nominal estimates with the stated source/load are about 1.07 dB passband loss and 32.8 dB stopband attenuation for the base case, and 1.49 dB and 45.3 dB for the higher-attenuation case. Confirm the plotted response in your installed Qucs-S/Ngspice version before release.

The article describes EMC filter simulation, common/differential-mode noise, parasitics, and damping. These schematics apply its AC-response/ideal-vs-practical evaluation approach to the Set A sensor low-pass requirement; they are not a component-for-component copy of the article's separate EMC mains filter.
