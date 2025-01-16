#include "Score.h"
#include "DxLib.h"

Score::Score() : playerScore(0), cpuScore(0) {}

void Score::AddPlayerScore() {
    playerScore++;
}

void Score::AddCpuScore() {
    cpuScore++;
}

void Score::Draw() const {
    char buffer[128];
    sprintf_s(buffer, sizeof(buffer), "Player: %d", playerScore);  
    DrawString(400, 10, buffer, GetColor(255, 255, 255));

    sprintf_s(buffer, sizeof(buffer), "CPU: %d", cpuScore);  
    DrawString(100, 10, buffer, GetColor(255, 255, 255));
}

bool Score::IsGameOver() const {
    return playerScore >= winScore || cpuScore >= winScore;
}

void Score::Reset() {
    playerScore = 0;
    cpuScore = 0;
}
