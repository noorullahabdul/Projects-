%% 800 V DC-Link Gate 2 analytical verification
% Standalone MATLAB script. No Simulink or toolbox is required.
clear; clc;

Vpack = [600 800 850];
Rpre  = [90.25 95 99.75];
Cdc   = [900e-6 1000e-6 1100e-6];
Rdis  = [900 1000 1100];

precharge = [];
for v = Vpack
    for r = Rpre
        for c = Cdc
            i0 = v/r;
            p0 = v^2/r;
            energy = 0.5*c*v^2;
            t90 = -r*c*log(0.1);
            precharge = [precharge; v r c i0 p0 energy t90 i0<=10 t90<=0.35]; %#ok<AGROW>
        end
    end
end

discharge = [];
for v = Vpack
    for r = Rdis
        for c = Cdc
            t60 = r*c*log(v/60);
            discharge = [discharge; v r c v^2/r 0.5*c*v^2 t60 t60<=5]; %#ok<AGROW>
        end
    end
end

PrechargeTable = array2table(precharge,'VariableNames', ...
    {'Vpack_V','Rpre_ohm','Cdc_F','I0_A','P0_W','Energy_J','T90_s','CurrentPass','TimePass'});
DischargeTable = array2table(discharge,'VariableNames', ...
    {'Vstart_V','Rdis_ohm','Cdc_F','P0_W','Energy_J','T60_s','Pass'});

assert(all(PrechargeTable.CurrentPass),'Precharge current limit failed');
assert(all(PrechargeTable.TimePass),'Precharge time limit failed');
assert(all(DischargeTable.Pass),'Active discharge time failed');

writetable(PrechargeTable,'matlab_precharge_results.csv');
writetable(DischargeTable,'matlab_discharge_results.csv');

fprintf('Precharge corners: %d/%d pass\n',sum(PrechargeTable.CurrentPass & PrechargeTable.TimePass),height(PrechargeTable));
fprintf('Maximum current: %.3f A\n',max(PrechargeTable.I0_A));
fprintf('Maximum t90: %.3f ms\n',1000*max(PrechargeTable.T90_s));
fprintf('Discharge corners: %d/%d pass\n',sum(DischargeTable.Pass),height(DischargeTable));
fprintf('Maximum t60: %.3f s\n',max(DischargeTable.T60_s));

figure('Color','w');
t = linspace(0,0.5,5000);
plot(t,800*(1-exp(-t/(100*1000e-6))),'LineWidth',1.8); grid on;
xlabel('Time (s)'); ylabel('DC-link voltage (V)'); title('Nominal 800 V Precharge');

