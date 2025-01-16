#ifndef GAME_H
#define GAME_H

#include "DxLib.h"
#include "GameState.h"
#include "Score.h"  // Score �N���X�̃C���N���[�h

class Paddle;
class Ball;
class Score;

class Game {
public:
    // �R���X�g���N�^
    Game();

    // �X�V����
    GameState Update();

    // ���Z�b�g����
    void Reset();
};

#endif // GAME_H
