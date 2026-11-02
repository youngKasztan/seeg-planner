<!-- nav:crumb -->
[Docs home](../README.md) › [Robot and configuration](README.md) › **Robot and electrode settings**
<!-- /nav:crumb -->

# Robot and electrode settings

## [robot]

| Key | Default | Meaning | Where it acts |
|---|---|---|---|
| `diameter_mm` | 2.0 | outer diameter. Its radius (1 mm) is added to every no-go margin; the full diameter is part of the gap between two paths | [safety maps](../05-path-planning/safety-maps.md), [path conflicts](../05-path-planning/choosing-the-paths-milp.md), tube radius in the export |
| `max_length_mm` | 150.0 | longest inserted length from the skin to the tip (straight + arc 1 + arc 2) | length penalty, [final check](../05-path-planning/final-check.md), straight-entry search |
| `min_straight_mm` | 15.0 | the straight part is at least this long (skin and bone) | straight-part penalty, final check; no electrode contacts in this part |
| `max_entry_angle_deg` | 30.0 | max angle between the robot axis and the skin normal at the entry | angle penalty, final check, straight-entry search |
| `arc1_max_length_mm` | 35.0 | arc 1 longest extension | optimiser bounds |
| `arc1_min_radius_mm` | 50.0 | arc 1 tightest bend | optimiser bounds; reference radius of the bending cost |
| `arc2_max_length_mm` | 35.0 | arc 2 longest extension | optimiser bounds, final check |
| `arc2_min_radius_mm` | 30.0 | arc 2 tightest bend | optimiser bounds, final check, [order test for groups](../05-path-planning/several-targets-on-one-path.md) |

**Effect of changes:** a larger diameter makes every zone effectively bigger; tighter minimum radii allow paths around obstacles but cost more bending; a shorter `max_length_mm` excludes deep targets from far entries.

## [electrode]

The robot carries an SEEG electrode with discrete recording contacts. See [Electrode contacts](../05-path-planning/electrode-contacts.md).

| Key | Default | Meaning |
|---|---|---|
| `contact_spacing_mm` | 5.0 | centre-to-centre distance between neighbouring contacts, measured along the curved path |
| `contact_length_mm` | 2.0 | length of one contact (drawn as a band) |
| `first_contact_mm` | 0.0 | centre of contact 1 measured back from the tip (the tip sits on the last target) |
| `n_contacts` | 0 | number of contacts; 0 = along the whole path up to the straight entry |
| `on_target_mm` | 1.5 | a target counts as recorded when a contact centre is at most this far from it (half a contact + 0.5 mm) |

<!-- nav:bar -->
---
← [The configuration file robot.toml](configuration-file.md) | [↑ Robot and configuration](README.md) | [Planner settings](config-planning.md) →
<!-- /nav:bar -->
