#ifndef GAME_H
#define GAME_H

#include "DxLib.h"
#include "GameState.h"
#include "Score.h"  

class Paddle;
class Ball;
class Score;

class Game {
public:
    
    Game();

    // 更新処理
    GameState Update();

    // リセット処理
    void Reset();
};

#endif // GAME_H
