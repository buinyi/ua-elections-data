SELECT 'polling_stations' AS table_name, COUNT(*) AS rows FROM polling_stations
UNION SELECT 'parties' AS table_name, COUNT(*) AS rows FROM parties
UNION SELECT 'candidates_individual' AS table_name, COUNT(*) AS rows FROM candidates_individual
UNION SELECT 'results_station' AS table_name, COUNT(*) AS rows FROM results_station
UNION SELECT 'results_competitor' AS table_name, COUNT(*) AS rows FROM results_competitor
ORDER BY 1;