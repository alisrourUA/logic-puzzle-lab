# Results (openai)

Model: gpt-4o-mini  |  generation runs: 120

## A. Prompting (0 / 1 / 3 examples)

| shots | n | valid first try | valid within 2 repairs | valid after all repairs | median #solutions on first try | avg repair rounds |
|---|---|---|---|---|---|---|
| 0 | 12 | 0% | 50% | 75% | 13 | 2.67 |
| 1 | 12 | 0% | 42% | 83% | 9 | 2.83 |
| 3 | 12 | 17% | 50% | 75% | 3 | 2.33 |

## B. Temperature

| T | n | valid first try | valid within 2 repairs | valid after all repairs | median #solutions on first try | first-try format errors | theme diversity | duplicate puzzles |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 12 | 0% | 58% | 75% | 10.0 | 0% | 16% | 0% |
| 0.4 | 12 | 0% | 25% | 75% | 7.5 | 0% | 59% | 0% |
| 0.8 | 12 | 0% | 33% | 75% | 10.0 | 0% | 72% | 0% |
| 1.2 | 12 | 8% | 58% | 83% | 10 | 17% | 84% | 0% |

## C. Difficulty control

| requested | n | valid | measured easy | medium | hard | mean score | mean clues |
|---|---|---|---|---|---|---|---|
| easy | 12 | 9 | 6 | 1 | 2 | 10.8 | 11.3 |
| medium | 12 | 8 | 6 | 2 | 0 | 6.6 | 11.0 |
| hard | 12 | 9 | 4 | 3 | 2 | 12.0 | 10.9 |

## D. Repair loop & self-verification

- valid on first try: 5%  ->  after repair: 76%
- first-try outcomes: valid 5%, several solutions 78%, contradiction 15%, broken format 2%
- LLM said **"my puzzle is unique"** 117 times; it was wrong 111 times (**95%**) - the solver caught every one.
- tokens used: 1,070,151 total, 11,760 per valid puzzle

## E. Solving (Part 2)

| method | solved (all) | easy | medium | hard | cell accuracy | avg steps | avg tokens |
|---|---|---|---|---|---|---|---|
| Plain prompt | 0% | 0% | 0% | 0% | 40% | 1.0 | 296 |
| Chain-of-thought | 8% | 12% | 0% | 12% | 48% | 1.0 | 1,204 |
| ReAct + tools | 75% | 88% | 88% | 50% | 89% | 4.9 | 5,094 |
