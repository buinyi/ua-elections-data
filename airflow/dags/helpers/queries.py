class SqlQueries:
    candidates_individual_table = {
        'staging': {
            'create':
                """CREATE TABLE IF NOT EXISTS candidates_individual_staging
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                ballot_type VARCHAR(20),
                district_id VARCHAR(5) DISTKEY,
                name VARCHAR(300),
                info VARCHAR(3000),
                nominated_by VARCHAR(300),
                reg_date VARCHAR(300),
                cancel_date VARCHAR(300)
                )
                SORTKEY (district_id, campaign, name);
                """,
        'drop': """DROP TABLE IF EXISTS candidates_individual_staging;"""
        },
        'prod': {
            'create':
                """CREATE TABLE IF NOT EXISTS candidates_individual
                (id BIGINT IDENTITY(1000000,1),
                campaign VARCHAR(20),
                ballot_type VARCHAR(20),
                district_id INT DISTKEY,
                name VARCHAR(300),
                info VARCHAR(3000),
                birth_year INT,
                nominated_by VARCHAR(300),
                reg_date VARCHAR(300),
                cancel_date VARCHAR(300)
                )
                SORTKEY (district_id, campaign, name);
                """,
            'insert':
                """INSERT INTO candidates_individual
                (campaign, ballot_type, district_id, name, info, birth_year, nominated_by, reg_date, cancel_date)
                SELECT
                campaign,
                ballot_type,
                CASE WHEN TRIM(district_id) ~ '^[0-9]+$' THEN TRIM(district_id) ELSE NULL END::INT as district_id,
                name,
                info,
                CASE WHEN LEFT(TRIM(SPLIT_PART(info, ' ', 4)),4) ~ '^[0-9]+$' THEN LEFT(TRIM(SPLIT_PART(info, ' ', 4)),4) ELSE NULL END::INT as birth_year,
                nominated_by,
                reg_date,
                cancel_date
                FROM candidates_individual_staging""",
            'drop': """DROP TABLE IF EXISTS candidates_individual;""",
            'check_id': """SELECT NOT EXISTS (SELECT 1 FROM candidates_individual WHERE id<1000000 AND campaign='{}');""",
            'check_num_rows': """SELECT COUNT(DISTINCT id) FROM candidates_individual WHERE campaign='{}';""",
            'check_duplicate_names_and_byears':
                """SELECT NOT EXISTS 
                    (SELECT name, birthday_year, campaign, ballot_type, district_id, SUM(1)
                    FROM candidates_individual 
                    GROUP BY 1,2,3,4,5
                    HAVING SUM(1)>1)"""
        },
    }

    parties_table = {
        'staging': {
            'create': """CREATE TABLE IF NOT EXISTS parties_staging
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                reg_date VARCHAR(20),
                ballot_rank VARCHAR(5),
                party VARCHAR(300),
                num_candidates VARCHAR(5)
                )
                SORTKEY (campaign, party);
                """,
        'drop': """DROP TABLE IF EXISTS parties_staging;"""
        },
        'prod': {
            'create':
                """CREATE TABLE IF NOT EXISTS parties
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                reg_date VARCHAR(20),
                ballot_rank INT,
                party VARCHAR(300),
                num_candidates INT
                )
                SORTKEY (campaign, party);
                """,
            'insert':
                """INSERT INTO parties
                (campaign, reg_date, ballot_rank, party, num_candidates)
                SELECT 
                campaign,
                reg_date, 
                CASE WHEN TRIM(ballot_rank) ~ '^[0-9]+$' THEN TRIM(ballot_rank) ELSE NULL END::INT,
                party,
                CASE WHEN TRIM(num_candidates) ~ '^[0-9]+$' THEN TRIM(num_candidates) ELSE NULL END::INT
                FROM parties_staging""",
            'drop': """DROP TABLE IF EXISTS parties;""",
            'check_id': """SELECT NOT EXISTS (SELECT 1 FROM parties WHERE id>=1000000 AND campaign='{}');""",
            'check_num_rows': """SELECT COUNT(DISTINCT id) FROM parties WHERE campaign='{}';"""
        }
    }

    results_station_table = {
        'staging': {
            'create':
                """CREATE TABLE IF NOT EXISTS results_station_staging
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                ballot_type VARCHAR(20),
                district_id VARCHAR(5) DISTKEY,
                station_id VARCHAR(30),
                ballots_available VARCHAR(20),
                ballots_not_used VARCHAR(20),
                voters_in_list VARCHAR(20),
                voters_in_list_add VARCHAR(20),
                ballots_received_at_station VARCHAR(20),
                ballots_received_other_places VARCHAR(20),
                ballots_received_total VARCHAR(20),
                ballots_in_ballot_boxes VARCHAR(150),
                ballots_not_counted VARCHAR(20),
                voted_at_station VARCHAR(20),
                voted_other_places VARCHAR(20),
                voted_total VARCHAR(20),
                votes_invalid VARCHAR(20),
                votes_positive_total VARCHAR(20),
                protocol_signed_date VARCHAR(20) 
                )
                SORTKEY (district_id, campaign, ballot_type, station_id);
                """,
            'drop': """DROP TABLE IF EXISTS results_station_staging;"""},
        'prod': {
            'create':
                """CREATE TABLE IF NOT EXISTS results_station
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                ballot_type VARCHAR(20),
                district_id INT DISTKEY,
                station_id VARCHAR(7),
                is_voting_valid BOOLEAN,
                ballots_available INT,
                ballots_not_used INT,
                voters_in_list INT,
                voters_in_list_add INT,
                ballots_received_at_station INT,
                ballots_received_other_places INT,
                ballots_received_total INT,
                ballots_in_ballot_boxes VARCHAR(150),
                ballots_not_counted INT,
                voted_at_station INT,
                voted_other_places INT,
                voted_total INT,
                votes_invalid INT,
                votes_positive_total INT,
                protocol_signed_date VARCHAR(20) 
                )
                SORTKEY (district_id, campaign, ballot_type, station_id);
                """,
            'insert': """INSERT INTO results_station
                (campaign,
                ballot_type,
                district_id,
                station_id,
                is_voting_valid,
                ballots_available,
                ballots_not_used,
                voters_in_list,
                voters_in_list_add,
                ballots_received_at_station,
                ballots_received_other_places,
                ballots_received_total,
                ballots_in_ballot_boxes,
                ballots_not_counted,
                voted_at_station,
                voted_other_places,
                voted_total,
                votes_invalid,
                votes_positive_total,
                protocol_signed_date
                )
                SELECT 
                campaign,
                ballot_type,
                CASE WHEN TRIM(district_id) ~ '^[0-9]+$' THEN TRIM(district_id) ELSE NULL END::INT,
                split_part(station_id,' ',1) AS station_id,
                CASE WHEN LOWER(TRIM(SUBSTRING(TRIM(station_id),7))) ILIKE 'не%дійсн%' THEN TRUE ELSE FALSE END, 
                CASE WHEN TRIM(ballots_available) ~ '^[0-9]+$' THEN TRIM(ballots_available) ELSE NULL END::INT,
                CASE WHEN TRIM(ballots_not_used) ~ '^[0-9]+$' THEN TRIM(ballots_not_used) ELSE NULL END::INT,
                CASE WHEN TRIM(voters_in_list) ~ '^[0-9]+$' THEN TRIM(voters_in_list) ELSE NULL END::INT,
                CASE WHEN TRIM(voters_in_list_add) ~ '^[0-9]+$' THEN TRIM(voters_in_list_add) ELSE NULL END::INT,
                CASE WHEN TRIM(ballots_received_at_station) ~ '^[0-9]+$' THEN TRIM(ballots_received_at_station) ELSE NULL END::INT,
                CASE WHEN TRIM(ballots_received_other_places) ~ '^[0-9]+$' THEN TRIM(ballots_received_other_places) ELSE NULL END::INT,
                CASE WHEN TRIM(ballots_received_total) ~ '^[0-9]+$' THEN TRIM(ballots_received_total) ELSE NULL END::INT,
                ballots_in_ballot_boxes,
                CASE WHEN TRIM(ballots_not_counted) ~ '^[0-9]+$' THEN TRIM(ballots_not_counted) ELSE NULL END::INT,
                CASE WHEN TRIM(voted_at_station) ~ '^[0-9]+$' THEN TRIM(voted_at_station) ELSE NULL END::INT,
                CASE WHEN TRIM(voted_other_places) ~ '^[0-9]+$' THEN TRIM(voted_other_places) ELSE NULL END::INT,
                CASE WHEN TRIM(voted_total) ~ '^[0-9]+$' THEN TRIM(voted_total) ELSE NULL END::INT,
                CASE WHEN TRIM(votes_invalid) ~ '^[0-9]+$' THEN TRIM(votes_invalid) ELSE NULL END::INT,
                CASE WHEN TRIM(votes_positive_total) ~ '^[0-9]+$' THEN TRIM(votes_positive_total) ELSE NULL END::INT,
                protocol_signed_date 
                FROM results_station_staging r""",
            'drop': """DROP TABLE IF EXISTS results_station;"""
        }
    }

    results_competitor_table = {
        'staging': {
            'create':
                """CREATE TABLE IF NOT EXISTS results_competitor_staging
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                ballot_type VARCHAR(20),
                district_id VARCHAR(5) DISTKEY,
                station_id VARCHAR(30),
                competitor VARCHAR(300),
                votes VARCHAR(20) 
                )
                SORTKEY (district_id, campaign, ballot_type, station_id);
                """,
            'drop': """DROP TABLE IF EXISTS results_station_staging;"""
        },
        'prod': {
            'create':
                """CREATE TABLE IF NOT EXISTS results_competitor
                (id BIGINT IDENTITY(1,1),
                campaign VARCHAR(20),
                ballot_type VARCHAR(20),
                district_id INT DISTKEY,
                station_id VARCHAR(30),
                competitor_id BIGINT,
                votes INT 
                )
                SORTKEY (district_id, campaign, ballot_type, station_id);
                """,
            'insert': """INSERT INTO results_competitor
                (campaign, ballot_type, district_id, station_id, competitor_id, votes)
                SELECT
                    r.campaign,
                    r.ballot_type,
                    CASE WHEN TRIM(r.district_id) ~ '^[0-9]+$' THEN TRIM(r.district_id) ELSE NULL END::INT,
                    r.station_id,
                    c.id AS competitor_id,
                    CASE WHEN TRIM(r.votes) ~ '^[0-9]+$' THEN TRIM(r.votes) ELSE NULL END::INT
                FROM results_competitor_staging r 
                left join candidates_individual c 
                    ON (c.name=TRIM(SPLIT_PART(r.competitor, '(', 1))
                    AND c.campaign=r.campaign
                    AND c.district_id=r.district_id
                    AND (r.competitor NOT LIKE '%(%' OR CASE WHEN LEFT(TRIM(SPLIT_PART(r.competitor, '(', 2)),4) ~ '^[0-9]+$' THEN LEFT(TRIM(SPLIT_PART(r.competitor, '(', 2)),4) END::INT = c.birth_year)
                    )
                WHERE r.ballot_type = 'individual';
 
                INSERT INTO results_competitor
                (campaign, ballot_type, district_id, station_id, competitor_id, votes)
                SELECT
                    r.campaign,
                    r.ballot_type,
                    CASE WHEN TRIM(r.district_id) ~ '^[0-9]+$' THEN TRIM(r.district_id) ELSE NULL END::INT,
                    r.station_id,
                    p.id AS competitor_id,
                    CASE WHEN TRIM(r.votes) ~ '^[0-9]+$' THEN TRIM(r.votes) ELSE NULL END::INT
                FROM results_competitor_staging r
                LEFT JOIN parties p ON (UPPER(p.party)=UPPER(r.competitor) AND p.campaign=r.campaign)
                WHERE r.ballot_type = 'party';""",
            'drop': """DROP TABLE IF EXISTS results_station;""",
            'check_num_rows': """SELECT COUNT(*) FROM results_competitor WHERE campaign='{}';""",
            'check_NULLs':
                """SELECT NOT EXISTS (SELECT 1 FROM results_competitor WHERE campaign='{}' AND competitor_id IS NULL""",
        }
    }

    stations_table = {
        'staging': {
            'create':
                """CREATE TABLE IF NOT EXISTS polling_stations_staging
                (ps_area VARCHAR(300),
                ps_commissionadr VARCHAR(1000),
                ps_commissionlocation VARCHAR(1000),
                ps_desc VARCHAR(8000),
                ps_geodvk VARCHAR(100),
                ps_geodata VARCHAR(35000),
                ps_geopg VARCHAR(100),
                ps_num VARCHAR(300),
                ps_placevotingadr VARCHAR(3000),
                ps_placevotinglocation VARCHAR(10000),
                ps_size VARCHAR(100),
                ps_type VARCHAR(100),
                region_id VARCHAR(100)
                );
                """,
            'fix1': #  fixes 5 records to make sure region and locality can be inferred correctly
                '''INSERT INTO polling_stations_staging 
                SELECT 
                ps_area,
                ps_commissionadr,
                ps_commissionlocation,
                ps_desc,
                ps_geodvk,
                ps_geodata,
                ps_geopg,
                ps_num,
                CASE ps_placevotingadr 
                WHEN 'вул.Леніна, кімната школяра, смт Високе, Донецька обл., м.Макіївка, 86196' THEN 'вул.Леніна, кімната школяра, смт Високе, м.Макіївка, Донецька обл., 86196'
                WHEN 'вул.Чехова, 122, м.Джанкой, Автономна Республіка Крим, м.Джанкой, 96100' THEN 'вул.Чехова, 122, м.Джанкой, Автономна Республіка Крим, 96100'
                WHEN 'Закарпатська облость, місто Берегове вул.Мужайська, 41, Закарпатська обл.' THEN 'вул.Мужайська, 41, м.Берегове, Закарпатська обл., 90202'
                WHEN 'просп.Перемоги, 134А, м.Горлівка, Донецька область, Донецька обл., 84637' THEN 'просп.Перемоги, 134А, м.Горлівка, Донецька обл., 84637'
                WHEN 'вул.Мічуріна, 7, м.Амвросіївка, Амвросіївський р-н, Донецька область, Донецька обл., 87300' THEN 'вул.Мічуріна, 7, м.Амвросіївка, Амвросіївський р-н, Донецька обл., 87300'
                ELSE ps_placevotingadr END as ps_placevotingadr,
                ps_placevotinglocation,
                ps_size,
                ps_type,
                region_id
                FROM polling_stations_staging
                WHERE ps_placevotingadr IN ('вул.Леніна, кімната школяра, смт Високе, Донецька обл., м.Макіївка, 86196', 
                                            'вул.Чехова, 122, м.Джанкой, Автономна Республіка Крим, м.Джанкой, 96100',
                                            'Закарпатська облость, місто Берегове вул.Мужайська, 41, Закарпатська обл.',
                                            'просп.Перемоги, 134А, м.Горлівка, Донецька область, Донецька обл., 84637',
                                              'вул.Мічуріна, 7, м.Амвросіївка, Амвросіївський р-н, Донецька область, Донецька обл., 87300');
            
                DELETE FROM polling_stations_staging
                WHERE ps_placevotingadr IN ('вул.Леніна, кімната школяра, смт Високе, Донецька обл., м.Макіївка, 86196', 
                                            'вул.Чехова, 122, м.Джанкой, Автономна Республіка Крим, м.Джанкой, 96100',
                                            'Закарпатська облость, місто Берегове вул.Мужайська, 41, Закарпатська обл.',
                                            'просп.Перемоги, 134А, м.Горлівка, Донецька область, Донецька обл., 84637',
                                              'вул.Мічуріна, 7, м.Амвросіївка, Амвросіївський р-н, Донецька область, Донецька обл., 87300');''',
            'drop': """DROP TABLE IF EXISTS polling_stations_staging;"""
        },
        'prod': {
            'create':
                """CREATE TABLE IF NOT EXISTS polling_stations
                (id VARCHAR(6)  NOT NULL PRIMARY KEY,
                district_id INT DISTKEY,
                station_type VARCHAR(100),
                station_size VARCHAR(100),
                region VARCHAR(100),
                locality VARCHAR(100),
                voting_adress VARCHAR(3000),
                voting_location VARCHAR(1000),
                area_coordinates VARCHAR(35000),
                voting_coordinates VARCHAR(50)
                )
                SORTKEY (district_id, id);
                """,
            'insert':
                """INSERT INTO polling_stations
                SELECT LPAD(ps_num::int, 6, '0') AS id,
                ps_area::INT AS district_id,
                ps_type AS station_type,
                ps_size AS station_size,
                CASE WHEN ps_type NOT IN ('В/Ч за кордоном', 'Закордонна', 'На полярній станції') THEN
                  CASE TRIM(' ' FROM split_part(ps_placevotingadr,',',REGEXP_COUNT ( ps_placevotingadr, ',' )))
                  WHEN 'Автономна Республика Крим' THEN 'Автономна Республіка Крим'
                  WHEN 'Автономна Респубілка Крим' THEN 'Автономна Республіка Крим'
                  WHEN 'Автономна Рсепубліка Крим' THEN 'Автономна Республіка Крим'
                  WHEN 'Автономна республіка Крим' THEN 'Автономна Республіка Крим'
                  WHEN 'Автономной Республіки Крим' THEN 'Автономна Республіка Крим'
                  WHEN 'Житомирсьа обл.' THEN 'Житомирська обл.'
                  WHEN 'Київька обл.' THEN 'Київська обл.'
                  ELSE TRIM(' ' FROM split_part(ps_placevotingadr,',',REGEXP_COUNT ( ps_placevotingadr, ',' ))) END 
                END AS region,
            
                CASE WHEN ps_type not in ('В/Ч за кордоном', 'Закордонна', 'На полярній станції') THEN 
                  CASE WHEN TRIM(' ' FROM split_part(ps_placevotingadr,',',REGEXP_COUNT ( ps_placevotingadr, ',' ))) IN ('м.Київ', 'м.Севастополь')
                  THEN TRIM(' ' FROM split_part(ps_placevotingadr,',',REGEXP_COUNT ( ps_placevotingadr, ',' )))
                  ELSE 
                    CASE TRIM(' ' FROM split_part(ps_placevotingadr,',',REGEXP_COUNT ( ps_placevotingadr, ',' )-1))
                    WHEN 'м.Надвірна' THEN 'Надвірнянський р-н'
                    WHEN 'м.Рогатин' THEN 'Рогатинський р-н'
                    WHEN 'смт Верховина' THEN 'Верховинський р-н'
                    WHEN 'м. Судак' THEN 'м.Судак'
                    WHEN 'с.Багатівка' THEN 'м.Судак'
                    WHEN 'с.Дачне' THEN 'м.Судак'
                    WHEN 'с.Лісне' THEN 'м.Судак'
                    WHEN 'с.Сонячна Долина' THEN 'м.Судак'
                    WHEN 'смт Заозерне' THEN 'м.Євпаторія'
                    WHEN 'смт Новоозерне' THEN 'м.Євпаторія'
                    WHEN 'смт Мирний' THEN 'м.Євпаторія'
                    WHEN 'Ленінськиий р-н' THEN 'Ленінський р-н'
                    WHEN 'Кіровоградський р-н' THEN 'Кропивницький р-н'
                    WHEN 'м.Бар' THEN 'Барський р-н'
                    WHEN 'м.Донецк' THEN 'м.Донецьк'
                    WHEN 'смт Гостомель' THEN 'м.Ірпінь'
                    WHEN 'м.Львів-Винники' THEN 'м.Львів'
                    WHEN 'м.Бучач' THEN 'Бучацький р-н'
                    WHEN 'м.Зборів' THEN 'Зборівський р-н'
                    WHEN 'м.Монастириська' THEN 'Монастириський р-н'
                    WHEN 'смт Краснокутськ' THEN 'Краснокутський р-н'
                    WHEN 'м.Кіцмань' THEN 'Кіцманський р-н'
                    WHEN 'м.Кобеляки' THEN 'Кобеляцький р-н'
                    WHEN 'Перевалський р-н' THEN 'Перевальський р-н'
                    WHEN 'м.Свердловск' THEN 'м.Свердловськ'
                    WHEN 'Перемишлянський р-н.' THEN 'Перемишлянський р-н'
                    WHEN 'Антрацитвський р-н' THEN 'Антрацитівський р-н'
                    WHEN 'м.Мукачеве' THEN 'м.Мукачево'
                    WHEN 'Комінтернівський р-н' THEN 'Лиманський р-н'
                    WHEN 'Лутугинськй р-н' THEN 'Лутугинський р-н'
                    ELSE TRIM(' ' FROM split_part(ps_placevotingadr,',',REGEXP_COUNT ( ps_placevotingadr, ',' )-1)) END
                  END
                END AS locality,
                ps_placevotingadr AS voting_adress,
                ps_placevotinglocation AS voting_location,
                ps_geodata AS area_coordinates,
                ps_geopg AS voting_coordinates
                FROM polling_stations_staging;
                """,
            'drop': """DROP TABLE IF EXISTS polling_stations;""",
            'check1':
                """WITH groups_by_locality AS
                (SELECT region, locality, COUNT(DISTINCT id) AS stations_count
                FROM public.polling_stations
                GROUP BY 1,2
                ORDER BY 1,2
                )
                
                SELECT NOT EXISTS (SELECT 1 FROM groups_by_locality WHERE stations_count<2)""",
            'check2':
                """SELECT 
                COUNT(DISTINCT district_id) = 225 
                AND COUNT(DISTINCT station_type)=6 
                AND COUNT(DISTINCT station_size)=3 
                FROM polling_stations"""
        }
    }
