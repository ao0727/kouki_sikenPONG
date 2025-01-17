#include "Game.h"
#include "Paddle.h"
#include "Ball.h"
#include "Score.h"

// �p�h�����C���X�^���X
Paddle playerPaddle(50, 200);  // �v���C���[�̃p�h�� 
Paddle cpuPaddle(550, 200);    // CPU�̃p�h�� 
Score score;                   // �X�R�A
Ball ball(300, 240, score);    // �{�[���� Score 

Game::Game() {
   
}

GameState Game::Update() {
    // �v���C���[�̃p�h���̑���
    playerPaddle.Update(KEY_INPUT_W, KEY_INPUT_S);

    // CPU�̃p�h���̑���iAI�j
    cpuPaddle.AIControl(ball);

    // �{�[���̍X�V
    ball.Update();

    // �{�[���ƃp�h���̏Փˏ���
    ball.CheckCollision(playerPaddle, cpuPaddle);

    // �{�[���̕`��
    ball.Draw();

    // �p�h���̕`��
    playerPaddle.Draw();
    cpuPaddle.Draw();

    // �X�R�A�̕`��
    score.Draw();

    // �Q�[���I�[�o�[����
    if (score.IsGameOver()) {
        return GAME_OVER;  // �Q�[���I�[�o�[�ɂȂ�����GAME_OVER�ɑJ��
    }

    return PLAYING;  // �Q�[���𑱂���
}

void Game::Reset() {
    // �Q�[�������Z�b�g���鏈����ǉ�
    playerPaddle = Paddle(50, 200);  // �v���C���[�p�h���̈ʒu�����Z�b�g
    cpuPaddle = Paddle(550, 200);    // CPU�p�h���̈ʒu�����Z�b�g
    ball.Reset(300, 240);            // �{�[���̈ʒu�����Z�b�g
    score.Reset();                   // �X�R�A�����Z�b�g
}
