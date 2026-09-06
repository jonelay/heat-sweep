# ORNL 2004 Prius Drivetrain Characterization

Measured drivetrain loss and back-EMF data from ORNL testing of the 2004
Toyota Prius (NHW20) hybrid electric drive system.

## Source

> R. H. Staunton, C. W. Ayers, J. N. Chiasson, T. A. Burress, and
> L. D. Marlino, "Evaluation of 2004 Toyota Prius Hybrid Electric Drive
> System — Interim Report," ORNL/TM-2004/247, Oak Ridge National
> Laboratory, 2005.

U.S. Department of Energy publication, contract DE-AC05-00OR22725.
Public domain.

Available from OSTI.gov.

## Files

### motor_back_emf_vs_speed.csv

**MG2, the traction motor.** Table 3.4 (p. 21). Back-EMF voltage vs
speed, 12 points from 502-5998 rpm. Differential gears blocked, oil at
25 degC. Vpeak/Vrms ratio exceeds sqrt(2) due to harmonic content.

| Column | Unit | Description |
|--------|------|-------------|
| `speed_rpm` | rpm | Motor shaft speed |
| `frequency_Hz` | Hz | Electrical frequency |
| `v_rms_V` | V | Scaled back-EMF (rms) |
| `v_peak_V` | V | Scaled back-EMF (peak) |

### generator_back_emf_vs_speed.csv

**MG1, the generator.** Table 3.5 (p. 22). Back-EMF voltage vs speed, 11
points from 1070-6420 rpm generator shaft speed. Different test setup
from the motor table: the engine shaft was held so the planetary carrier
could not rotate, which links the generator to the gear train, and the
nominal oil temperature was 80 degC rather than 25.

Because the generator is driven through the planetary from the axle,
ORNL tabulates axle speed and axle torque alongside generator speed.
Both are kept: the axle columns are the test's independent variable, and
the gear ratio between them is a transcription check.

| Column | Unit | Description |
|--------|------|-------------|
| `axle_speed_rpm` | rpm | Axle speed, the swept variable |
| `gen_speed_rpm` | rpm | Generator shaft speed |
| `axle_torque_Nm` | Nm | Axle torque during the run |
| `frequency_Hz` | Hz | Electrical frequency |
| `v_rms_V` | V | Scaled back-EMF (rms) |
| `v_peak_V` | V | Scaled back-EMF (peak) |

Validation of the transcription, all 11 rows:
- Pole pairs from `frequency_Hz / (gen_speed_rpm / 60)`: 3.93-4.09,
  i.e. 4, matching the 8-pole machine ORNL describes
- `gen_speed_rpm / axle_speed_rpm` = 10.70 exactly at every row
- Voltage constant `v_rms_V / frequency_Hz`: 0.451-0.474 Vrms/Hz,
  mean 0.460, against the 0.46 Vrms/Hz ORNL states in its summary
- Vpeak/Vrms 1.56-1.67, above sqrt(2), same harmonic signature as the
  motor table

### system_loss_breakdown_25C.csv

Table 3.7 (p. 22). Hybrid drive system loss decomposition at ~25 degC
oil temperature, 12 speed points. Losses separated by component:
gears, motor rotor, and planetary/generator/sun gear.

| Column | Unit | Description |
|--------|------|-------------|
| `speed_rpm` | rpm | Motor shaft speed |
| `p_gear_W` | W | Main drive gear + chain + differential losses |
| `p_rotor_W` | W | Motor rotor losses (windage + eddy) |
| `p_planetary_gen_sun_W` | W | Planetary gear + generator rotor + sun gear losses |
| `p_total_W` | W | Total system loss |

### drivetrain_loss_vs_temp.csv

Tables 3.8-3.13 (pp. 23-25). Configuration B losses (gear + planetary
+ generator; motor rotor removed) vs speed at 6 oil temperatures
(28/40/50/60/70/80 degC), 12 speed points each. 72 rows total.

Losses decrease ~20% from 28 to 80 degC (oil viscosity drop).

| Column | Unit | Description |
|--------|------|-------------|
| `t_oil_nominal_C` | degC | Nominal oil temperature for the test run |
| `speed_rpm` | rpm | Motor shaft speed |
| `t_oil_actual_C` | degC | Actual oil temperature during measurement |
| `p_loss_W` | W | Configuration B losses |

## Extraction method

Transcribed from the PDF tables. Verified against the markdown
conversion; all tables are clean with consistent format.
