function build_dclink_model()
% Programmatically creates a portable Simulink model shell for the 800 V
% DC-link plant. Run in MATLAB with Simulink. Simscape Electrical blocks may
% be substituted for the reduced-order transfer-function plant.

mdl = 'DCLINK_800V_OEM_PORTFOLIO';
if bdIsLoaded(mdl), close_system(mdl,0); end
new_system(mdl); open_system(mdl);

add_block('simulink/Sources/Step',[mdl '/PackVoltage'], ...
    'Time','0','Before','0','After','800','Position',[40 70 90 100]);
add_block('simulink/Continuous/Transfer Fcn',[mdl '/PrechargePlant'], ...
    'Numerator','[1]','Denominator','[0.1 1]','Position',[180 65 300 105]);
add_block('simulink/Sinks/Scope',[mdl '/DCLinkScope'], ...
    'Position',[390 65 440 105]);
add_line(mdl,'PackVoltage/1','PrechargePlant/1');
add_line(mdl,'PrechargePlant/1','DCLinkScope/1');

set_param(mdl,'StopTime','0.5','Solver','ode23t');
save_system(mdl,[mdl '.slx']);
disp(['Created ' mdl '.slx. Replace reduced plant with reviewed Simscape hardware model before claiming correlation.']);
end

