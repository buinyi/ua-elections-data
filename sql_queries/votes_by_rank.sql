-- Redshift orders Ukrainian characters incorrectly, so manual ordering is implemented here
WITH records AS (SELECT campaign, ballot_type, district_id, id, name,
ROW_NUMBER() OVER(PARTITION BY campaign, ballot_type, district_id
    ORDER BY CASE WHEN LEFT(name,1) IN ('А','Б','В','Г','Д','Е') THEN 1
      WHEN LEFT(name,1) IN ('Є') THEN 2
      WHEN LEFT(name,1) IN ('Ж','З') THEN 3
      WHEN LEFT(name,1) IN ('І') THEN 4
      ELSE 5 END ASC,
      CASE WHEN UPPER(SUBSTRING(name,2,1)) IN ('А','Б','В','Г','Д','Е') THEN 1
      WHEN UPPER(SUBSTRING(name,2,1)) IN ('Є') THEN 2
      WHEN UPPER(SUBSTRING(name,2,1)) IN ('Ж','З') THEN 3
      WHEN UPPER(SUBSTRING(name,2,1)) IN ('І') THEN 4
      ELSE 5 END ASC,
      SUBSTRING(name,3,100) ASC) as rank_asc,
ROW_NUMBER() OVER(PARTITION BY campaign, ballot_type, district_id
    ORDER BY CASE WHEN LEFT(name,1) IN ('А','Б','В','Г','Д','Е') THEN 1
      WHEN LEFT(name,1) IN ('Є') THEN 2
      WHEN LEFT(name,1) IN ('Ж','З') THEN 3
      WHEN LEFT(name,1) IN ('І') THEN 4
      ELSE 5 END DESC,
      CASE WHEN UPPER(SUBSTRING(name,2,1)) IN ('А','Б','В','Г','Д','Е') THEN 1
      WHEN UPPER(SUBSTRING(name,2,1)) IN ('Є') THEN 2
      WHEN UPPER(SUBSTRING(name,2,1)) IN ('Ж','З') THEN 3
      WHEN UPPER(SUBSTRING(name,2,1)) IN ('І') THEN 4
      ELSE 5 END DESC,
      SUBSTRING(name,3,100) DESC) as rank_desc
FROM candidates_individual
WHERE ballot_type='individual'
ORDER by 1,2
)

SELECT c.campaign, rank_asc, SUM(c.votes) AS votes, SUM(s.votes_positive_total),
SUM(c.votes) /SUM(s.votes_positive_total)
FROM results_competitor c
JOIN results_station s ON c.campaign=s.campaign and c.ballot_type=s.ballot_type
	AND c.district_id=s.district_id AND c.station_id = s.station_id
JOIN records r ON c.competitor_id = r.id AND c.campaign=r.campaign and c.ballot_type=r.ballot_type
	AND c.district_id=r.district_id
WHERE rank_asc<=5
GROUP BY 1,2
ORDER BY 1,2
