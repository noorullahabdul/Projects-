function modelFile = build_dclink_simscape_model(outputFolder)
%BUILD_DCLINK_SIMSCAPE_MODEL Create the 800 V electrical plant model.
% Requires Simulink and Simscape. Foundation Library block paths are used.
% The script checks each block path and stops with a clear compatibility
% message if the installed MATLAB release uses a different library path.

if nargin < 1, outputFolder = pwd; end
assert(license('test','Simulink')==1,'Simulink license is required.');
assert(exist('ssc_new','file')==2,'Simscape is required (ssc_new not found).');
if ~exist(outputFolder,'dir'), mkdir(outputFolder); end

mdl='DCLINK_800V_SIMSCAPE';
modelFile=fullfile(outputFolder,[mdl '.slx']);
if bdIsLoaded(mdl), close_system(mdl,0); end
if exist(modelFile,'file'), delete(modelFile); end

% Creates a model with Solver Configuration, converters and reference blocks.
ssc_new(mdl,'electrical'); open_system(mdl);
set_param(mdl,'StopTime','6','Solver','ode23t','MaxStep','1e-4');

% Remove only the automatically generated demonstration subsystem if present.
demo=[mdl '/Simscape Network'];
if getSimulinkBlockHandle(demo)>0, delete_block(demo); end

lib.source='fl_lib/Electrical/Electrical Sources/DC Voltage Source';
lib.resistor='fl_lib/Electrical/Electrical Elements/Resistor';
lib.inductor='fl_lib/Electrical/Electrical Elements/Inductor';
lib.capacitor='fl_lib/Electrical/Electrical Elements/Capacitor';
lib.switch='fl_lib/Electrical/Electrical Elements/Controlled Switch';
lib.vsensor='fl_lib/Electrical/Electrical Sensors/Voltage Sensor';
lib.reference='fl_lib/Electrical/Electrical Elements/Electrical Reference';
lib.solver='nesl_utility/Solver Configuration';
lib.s2p='nesl_utility/Simulink-PS Converter';
lib.p2s='nesl_utility/PS-Simulink Converter';

fields=fieldnames(lib);
for k=1:numel(fields)
    try load_system(extractBefore(lib.(fields{k}),'/')); catch, end
    if getSimulinkBlockHandle(lib.(fields{k}))<0
        error('Block path unavailable in this MATLAB release: %s\nUse Library Browser to update lib.%s.',lib.(fields{k}),fields{k});
    end
end

% Electrical elements and approximate positions.
add_block(lib.source,[mdl '/HV_Battery'],'Position',[80 185 135 245]);
add_block(lib.resistor,[mdl '/Battery_ESR'],'Position',[180 190 245 240]);
add_block(lib.inductor,[mdl '/Bus_Inductance'],'Position',[285 190 350 240]);
add_block(lib.switch,[mdl '/Main_Contactor'],'Position',[405 160 475 230]);
add_block(lib.resistor,[mdl '/Precharge_Resistor'],'Position',[405 285 480 335]);
add_block(lib.switch,[mdl '/Precharge_Contactor'],'Position',[520 275 590 345]);
add_block(lib.resistor,[mdl '/Capacitor_ESR'],'Position',[650 190 720 240]);
add_block(lib.inductor,[mdl '/Capacitor_ESL'],'Position',[755 190 820 240]);
add_block(lib.capacitor,[mdl '/DC_Link_Capacitor'],'Position',[870 185 935 245]);
add_block(lib.switch,[mdl '/Discharge_Switch'],'Position',[675 365 745 435]);
add_block(lib.resistor,[mdl '/Active_Discharge_1k'],'Position',[805 375 885 425]);
add_block(lib.resistor,[mdl '/Passive_Bleeder_100k'],'Position',[965 285 1045 335]);
add_block(lib.vsensor,[mdl '/DC_Link_Voltage_Sensor'],'Position',[965 175 1045 245]);
add_block(lib.reference,[mdl '/Electrical_Reference'],'Position',[135 455 185 505]);
add_block(lib.solver,[mdl '/Solver_Configuration'],'Position',[245 450 315 510]);

% Parameters. Parameter names can differ slightly by release; set safely.
safeSet([mdl '/HV_Battery'],{'v0','800','V','800'});
safeSet([mdl '/Battery_ESR'],{'R','0.03','resistance','0.03'});
safeSet([mdl '/Bus_Inductance'],{'L','2e-6','inductance','2e-6'});
safeSet([mdl '/Precharge_Resistor'],{'R','92','resistance','92'});
safeSet([mdl '/Capacitor_ESR'],{'R','0.008','resistance','0.008'});
safeSet([mdl '/Capacitor_ESL'],{'L','100e-9','inductance','100e-9'});
safeSet([mdl '/DC_Link_Capacitor'],{'C','1000e-6','capacitance','1000e-6'});
safeSet([mdl '/Active_Discharge_1k'],{'R','1000','resistance','1000'});
safeSet([mdl '/Passive_Bleeder_100k'],{'R','100000','resistance','100000'});

% Physical network connections use conserving port handles, reducing
% dependence on displayed port names across MATLAB releases.
connectConserving(mdl,'HV_Battery','Battery_ESR');
connectConserving(mdl,'Battery_ESR','Bus_Inductance');
connectConserving(mdl,'Bus_Inductance','Main_Contactor');
connectConserving(mdl,'Main_Contactor','Capacitor_ESR');
connectConserving(mdl,'Capacitor_ESR','Capacitor_ESL');
connectConserving(mdl,'Capacitor_ESL','DC_Link_Capacitor');

% Precharge and discharge branches may require branch-line routing depending
% on release. Add annotations and leave explicit endpoints for local review.
add_block('built-in/Note',[mdl '/BRANCH_CONNECTIONS_REQUIRED'], ...
 'Position',[385 530 1040 620], ...
 'Text',['LOCAL REVIEW REQUIRED: connect Precharge Resistor + Contactor in parallel with Main Contactor; ' ...
 'connect Active Discharge and Passive Bleeder across DC link; connect negative terminals to Electrical Reference. ' ...
 'Controlled Switch gates require Simulink-PS Converter commands from the logical model.']);
add_block('built-in/Note',[mdl '/MODEL_LIMITATIONS'], ...
 'Position',[385 640 1040 720], ...
 'Text',['Replace ideal controlled switches with shortlisted contactor models. Add auxiliary-contact delay/bounce, ' ...
 'temperature dependence, measured ESR/ESL and validated insulation/fault behavior before correlation.']);

save_system(mdl,modelFile);
fprintf('Created Simscape plant model: %s\n',modelFile);
fprintf('Open the model and complete the clearly annotated branch/control connections for your MATLAB release.\n');
end

function safeSet(block,pairs)
for k=1:2:numel(pairs)
    try set_param(block,pairs{k},pairs{k+1}); return; catch, end
end
warning('Parameter name differs by release for %s; set value manually.',block);
end

function connectConserving(mdl,a,b)
pa=get_param([mdl '/' a],'PortHandles'); pb=get_param([mdl '/' b],'PortHandles');
ha=[pa.LConn(:);pa.RConn(:)]; hb=[pb.LConn(:);pb.RConn(:)];
if isempty(ha)||isempty(hb), error('No conserving ports found for %s or %s.',a,b); end
add_line(mdl,ha(end),hb(1),'autorouting','on');
end

