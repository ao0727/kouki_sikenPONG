#ifndef GAME_H
#define GAME_H

#include "DxLib.h"
#include "GameState.h"
#include "Score.h"  // Score クラスのインクルード

class Paddle;
class Ball;
class Score;

class Game {
public:
    // コンストラクタ
    Game();

    // 更新処理
    GameState Update();

    // リセット処理
    void Reset();
};

#endif // GAME_H
