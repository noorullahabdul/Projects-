%% DCLINK_GATE3_CORNER_CAMPAIGN - OEM-style analytical verification campaign
% Base MATLAB only. Generates deterministic corners, 50k Monte Carlo cases,
% fault-oriented cases, plots, CSV evidence and a machine-readable MAT file.
% IMPORTANT: results are valid only after this script is executed locally and
% the evidence register is updated with MATLAB release, host and file hashes.

clear; clc; close all;
rng(8002026,'twister');
outDir = fullfile(fileparts(mfilename('fullpath')),'generated_evidence');
if ~exist(outDir,'dir'), mkdir(outDir); end

%% Controlled design inputs
lim.Vmin=600; lim.Vmax=850; lim.IpreMax=10; lim.tPreMax=0.350;
lim.actualRatioMin=0.90; lim.Vsafe=60; lim.tDisMax=5.0;
nom.Rpre25=92; nom.tcRpre=100e-6; nom.Cdc=1.0e-3;
nom.Rdis25=1000; nom.tcRdis=500e-6; nom.sensorErr=0.015;
nom.Rsource=47e-3; nom.Rcont=0.85e-3; nom.threshold=0.93;

% Independent factors: voltage, C tolerance/ageing/bias, resistor tolerance,
% temperature, sensor errors, source impedance and contactor command delay.
Vpack=[600 800 850]; Cdc=[0.90 1.00 1.10]*nom.Cdc;
Rpre25=[0.97 1 1.03]*nom.Rpre25; Temp=[-40 25 105];
PackErr=[-nom.sensorErr 0 nom.sensorErr]; LinkErr=[-nom.sensorErr 0 nom.sensorErr];
Rsource=[25e-3 nom.Rsource 150e-3]; CmdDelay=[0 2.5e-3 5e-3];

%% Full-factorial deterministic corners (3^8 = 6561)
[V,C,R,T,Ep,Ed,Rs,Td]=ndgrid(Vpack,Cdc,Rpre25,Temp,PackErr,LinkErr,Rsource,CmdDelay);
Rtemp=R.*(1+nom.tcRpre.*(T-25));
Rtotal=Rtemp+Rs+nom.Rcont;
actualRatio=min(nom.threshold.*(1+Ep)./(1+Ed),0.999999);
tCmd=Td-Rtotal.*C.*log(1-actualRatio);
I0=V./Rtotal; Ppre=I0.^2.*Rtemp; Estore=0.5.*C.*V.^2;
passI=I0<=lim.IpreMax; passT=tCmd<=lim.tPreMax;
passRatio=actualRatio>=lim.actualRatioMin;

CornerTable=table(V(:),C(:),R(:),T(:),Ep(:),Ed(:),Rs(:),Td(:), ...
 Rtemp(:),Rtotal(:),I0(:),Ppre(:),Estore(:),actualRatio(:),tCmd(:), ...
 passI(:),passT(:),passRatio(:),'VariableNames', ...
 {'Vpack_V','Cdc_F','Rpre25_Ohm','Temp_C','PackSensorError','LinkSensorError', ...
 'SourceResistance_Ohm','CommandDelay_s','RpreHot_Ohm','TotalResistance_Ohm', ...
 'InitialCurrent_A','InitialResistorPower_W','StoredEnergy_J','ActualRatio', ...
 'CommandTime_s','CurrentPass','TimingPass','RatioPass'});
CornerTable.Pass=CornerTable.CurrentPass & CornerTable.TimingPass & CornerTable.RatioPass;
writetable(CornerTable,fullfile(outDir,'matlab_deterministic_corners.csv'));

%% Active-discharge corners
Rdis25=[0.90 1.00 1.10]*nom.Rdis25;
[Vd,Cd,Rd,Td2]=ndgrid(Vpack,Cdc,Rdis25,Temp);
RdisHot=Rd.*(1+nom.tcRdis.*(Td2-25));
t60=RdisHot.*Cd.*log(Vd/lim.Vsafe);
Pdis0=Vd.^2./RdisHot;
DischargeTable=table(Vd(:),Cd(:),Rd(:),Td2(:),RdisHot(:),Pdis0(:),t60(:), ...
 t60(:)<=lim.tDisMax,'VariableNames',{'Vstart_V','Cdc_F','Rdis25_Ohm', ...
 'Temp_C','RdisHot_Ohm','InitialPower_W','TimeTo60V_s','Pass'});
writetable(DischargeTable,fullfile(outDir,'matlab_discharge_corners.csv'));

%% 50,000-case Monte Carlo with bounded distributions
N=50000;
mc.V=lim.Vmin+(lim.Vmax-lim.Vmin)*rand(N,1);
mc.C=nom.Cdc.*(0.90+0.20*rand(N,1));
mc.R25=nom.Rpre25.*(0.97+0.06*rand(N,1));
mc.T=-40+145*rand(N,1);
mc.Ep=-nom.sensorErr+2*nom.sensorErr*rand(N,1);
mc.Ed=-nom.sensorErr+2*nom.sensorErr*rand(N,1);
mc.Rs=25e-3+(150e-3-25e-3)*rand(N,1);
mc.Delay=5e-3*rand(N,1);
mc.R=mc.R25.*(1+nom.tcRpre.*(mc.T-25));
mc.Rtot=mc.R+mc.Rs+nom.Rcont;
mc.Ratio=min(nom.threshold.*(1+mc.Ep)./(1+mc.Ed),0.999999);
mc.I0=mc.V./mc.Rtot;
mc.t=mc.Delay-mc.Rtot.*mc.C.*log(1-mc.Ratio);
mc.Pass=mc.I0<=lim.IpreMax & mc.t<=lim.tPreMax & mc.Ratio>=lim.actualRatioMin;
MonteCarloTable=table((1:N)',mc.V,mc.C,mc.R25,mc.T,mc.Ep,mc.Ed,mc.Rs, ...
 mc.Delay,mc.I0,mc.t,mc.Ratio,mc.Pass,'VariableNames',{'CaseID','Vpack_V', ...
 'Cdc_F','Rpre25_Ohm','Temp_C','PackSensorError','LinkSensorError', ...
 'SourceResistance_Ohm','CommandDelay_s','InitialCurrent_A','CommandTime_s', ...
 'ActualRatio','Pass'});
writetable(MonteCarloTable,fullfile(outDir,'matlab_monte_carlo_50000.csv'));

%% Fault-oriented calculation set
FaultID=["F-NOM";"F-PRE-OPEN";"F-PRE-SHORT";"F-SNS-HIGH"; ...
 "F-SNS-LOW";"F-DIS-OPEN";"F-C-HIGH";"F-RSRC-HIGH"];
Expected=["Nominal sequence";"Timeout/no rise";"Overcurrent abort"; ...
 "Correlation inhibit";"Timeout/inhibit";"Unsafe decay DTC"; ...
 "Timing margin check";"Timing margin check"];
DetectionLimit_ms=[350;350;20;20;20;5000;350;350];
TestStatus=repmat("REQUIRES_LOGIC_OR_PLANT_RUN",numel(FaultID),1);
FaultTable=table(FaultID,Expected,DetectionLimit_ms,TestStatus);
writetable(FaultTable,fullfile(outDir,'matlab_fault_campaign.csv'));

%% Evidence summary and plots
Summary=table(height(CornerTable),sum(CornerTable.Pass),max(CornerTable.InitialCurrent_A), ...
 max(CornerTable.CommandTime_s),min(CornerTable.ActualRatio),height(DischargeTable), ...
 sum(DischargeTable.Pass),max(DischargeTable.TimeTo60V_s),N,sum(MonteCarloTable.Pass), ...
 'VariableNames',{'CornerCases','CornerPass','MaxCurrent_A','MaxCommandTime_s', ...
 'MinActualRatio','DischargeCases','DischargePass','MaxTimeTo60V_s', ...
 'MonteCarloCases','MonteCarloPass'});
writetable(Summary,fullfile(outDir,'matlab_gate3_summary.csv'));
save(fullfile(outDir,'dclink_gate3_campaign.mat'),'lim','nom','Summary', ...
 'CornerTable','DischargeTable','FaultTable','-v7.3');

f=figure('Color','w'); tiledlayout(2,2);
nexttile; histogram(1000*MonteCarloTable.CommandTime_s,80); xline(350,'r--'); grid on;
xlabel('Command time (ms)'); ylabel('Cases'); title('Precharge timing');
nexttile; histogram(MonteCarloTable.InitialCurrent_A,80); xline(10,'r--'); grid on;
xlabel('Initial current (A)'); ylabel('Cases'); title('Inrush current');
nexttile; scatter(CornerTable.RpreHot_Ohm,1e6*CornerTable.Cdc_F,8, ...
 1000*CornerTable.CommandTime_s,'filled'); colorbar; grid on;
xlabel('Rpre hot (Ohm)'); ylabel('Cdc (uF)'); title('Corner interaction');
nexttile; histogram(DischargeTable.TimeTo60V_s,30); xline(5,'r--'); grid on;
xlabel('Time to 60 V (s)'); ylabel('Cases'); title('Active discharge');
exportgraphics(f,fullfile(outDir,'matlab_gate3_corner_dashboard.png'),'Resolution',250);

fprintf('Deterministic: %d/%d pass\n',sum(CornerTable.Pass),height(CornerTable));
fprintf('Monte Carlo:   %d/%d pass\n',sum(MonteCarloTable.Pass),N);
fprintf('Discharge:     %d/%d pass\n',sum(DischargeTable.Pass),height(DischargeTable));
if ~all(CornerTable.Pass), warning('One or more deterministic corners failed.'); end
if ~all(MonteCarloTable.Pass), warning('One or more Monte Carlo cases failed.'); end
if ~all(DischargeTable.Pass), warning('One or more discharge corners failed.'); end
